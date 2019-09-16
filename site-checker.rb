#!/usr/bin/env ruby

require 'lumberg'
require 'net/http'
require 'uri'
require "webdrivers"
require "selenium-webdriver"
require 'yaml'
require 'fileutils'


class WhmChecker

  def initialize(config = {})
    config[:output_dir] ||= '.'
    @outputdir = config[:output_dir]
    @log = Logger.new(config[:logfile] || STDOUT, formatter: proc {|severity, datetime, progname, msg|
      "#{datetime} #{msg}\n"
    })
    @dns = Resolv::DNS.new
    @directory_format = config[:directory_format] || "%Y%m%d"
    @ip_whitelist = []
    @lastrun_file = config[:lastrun_file] || "lastrun.txt"

    selenium_options = Selenium::WebDriver::Chrome::Options.new
    selenium_options.add_argument('--headless')
    @driver = Selenium::WebDriver.for :chrome, options: selenium_options

    @read_timeout = 30
    @open_timeout = 30
  end

  def check_accounts(host, hash, date = Time.now.strftime(@directory_format))
    server = Lumberg::Whm::Server.new(
      host: host,
      hash: hash
    )

    directory = File.join(@outputdir, date, host)
    FileUtils.mkdir_p directory unless File.exists? directory

    account = server.account
    result  = account.list

    # Get a list of IP addresses we'll check
    ip_addr = server.list_ips

    unless ip_addr[:message].nil?
        @log.error "server.list_ips: #{ip_addr[:message]}"
        exit
    end

    if ip_addr[:params].is_a? Array
      @ip_whitelist = ip_addr[:params].collect {|a| a[:ip]}
    else
      @ip_whitelist = [ip_addr[:params][:ip]]
    end      

    result[:params][:acct].each do |acct|
      next if acct[:suspended]

      addon = Lumberg::Cpanel::AddonDomain.new(
        server:       server,  # An instance of Lumberg::Server
        api_username: acct[:user]  # User whose cPanel we'll be interacting with
      )

      domlist = []
      domains = []

      begin
        domlist = addon.list[:params][:data]
      rescue StandardError => ex
        @log.warn "host=#{host} user=#{acct[:user]} error=could_not_fetch_addons"
      end

      domlist.unshift(acct).each do |account_domain|
        result, message = check_in_whitelist(account_domain[:domain])
        if result
          domains << account_domain[:domain]
        else
          @log.warn "host=#{host} user=#{acct[:user]} domain=#{account_domain[:domain]} code=#{message}"
        end

      end

      domains.each do |dom|
        result = fetch_page(acct[:user], dom, directory)
        log = "host=#{host} user=#{acct[:user]} domain=#{dom}"
        log = log + " code=#{result[:code]}" if result.has_key? :code
        log = log + " location=#{result[:location]}" if result.has_key? :location
        log = log + " digest=#{result[:digest]}" if result.has_key? :digest
        @log.info(log)
      end
    end

    f = File.open(@lastrun_file, 'a')
    f.puts directory
    f.close
  end

  def check_in_whitelist(dom)
    begin
      ip = @dns.getaddress(dom)
    rescue Resolv::ResolvError
      return false, "unresolvable"
    end

    if @ip_whitelist.include? ip.to_s
      return true, nil
    else
      return false, "not_whitelisted"
    end
  end

  def fetch_page(user, dom, directory)
    uri = URI.parse("http://#{dom}")

    if File.exist?("#{directory}/#{user}-#{dom}.html") && File.exist?("#{directory}/#{user}-#{dom}.png")
      return {code: "skipped"}
    end

    begin
      location, response = fetch_url uri

      if response == 0
        return {location: location, code: "too_many_redirects"}
      end

      # Dump status and body
      f = File.new("#{directory}/#{user}-#{dom}.html", "w")
      f.puts location
      unless response.nil?
        f.puts response.code
        f.puts response.body
      end
      f.close

      return if response.code == 521

      # Dump image
      @driver.navigate.to location
      @driver.manage.window.resize_to(1440, 2000)
      @driver.save_screenshot "#{directory}/#{user}-#{dom}.png"
      return { location: location, code: response.code, digest: Digest::SHA2.hexdigest(response.body)  }
    rescue StandardError => ex
      return { code: ex.to_s }
    end
  end

  def fetch_url(uri, limit = 5)
    if limit == 0
      return 0, uri
    end

    uri.path = "/" if uri.path.empty?
    response = nil

    begin
      http = Net::HTTP.new(uri.host, uri.port)
      http.use_ssl = uri.instance_of?(URI::HTTPS)
      http.read_timeout = @read_timeout
      http.open_timeout = @open_timeout
      response = http.start { |http| http.get(uri.path) }
    rescue SocketError
      return 521, nil  # Server down
    end

    case response
    when Net::HTTPRedirection then
      location = response['location']
      l, r = fetch_url(URI(location), limit - 1)
      return l, r
    else
      return uri, response
    end

  end

end



configfile = 'servers.yml'
config = YAML::load(File.open(configfile))

whm = WhmChecker.new(config[:config])

config[:servers].each do |server|
  whm.check_accounts(server[:host], server[:hash])
end
