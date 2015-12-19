#!/usr/bin/env ruby

require 'lumberg'
require 'net/http'
require 'uri'
require 'phantomjs'
require 'yaml'
require 'fileutils'


class WhmChecker

  def initialize(config = {})
    config[:output_dir] ||= '.'
    @outputdir = config[:output_dir]
    @log = Logger.new(config[:logfile] || STDOUT)
    @dns = Resolv::DNS.new
    @ip_whitelist = []
  end

  def check_accounts(host, hash, date = Time.now.strftime("%Y%m%d"))
    @log.info "Checking host #{host}"
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
    @ip_whitelist = ip_addr[:params].collect {|a| a[:ip]}

    result[:params][:acct].each do |ac|
      next if ac[:suspended]


      addon = Lumberg::Cpanel::AddonDomain.new(
        server:       server,  # An instance of Lumberg::Server
        api_username: ac[:user]  # User whose cPanel we'll be interacting with
      )

      domlist = addon.list

      domains = []

      @log.info "Checking user #{ac[:user]}:"

      domains << ac[:domain] if check_in_whitelist(ac[:domain])

      domlist[:params][:data].each do |ad|
        domains << ad[:domain] if check_in_whitelist(ad[:domain])
      end

      domains.each do |dom|
        @log.info " - #{dom}"
        fetch_page(ac[:user], dom, directory)
      end

    end

  end

  def check_in_whitelist(domain)
    begin
      ip = @dns.getaddress(domain)
    rescue Resolv::ResolvError
      @log.warn "Skipping unresolvable #{domain}"
      return false
    end

    if @ip_whitelist.include? ip.to_s
      true
    else
      @log.warn "Skipping non-whitelisted #{domain}"
      false
    end
  end

  def fetch_page(user, dom, directory)
    uri = URI.parse("http://#{dom}")

    # SSL?
    response = fetch_url uri

    # Dump status and body
    f = File.new("#{directory}/#{user}-#{dom}.html", "w")
    f.puts response.code
    f.puts response.body
    f.close

    # Dump image

    js = "
      var page = require('webpage').create();
      page.viewportSize = {
        width: 1400,
        height: 1500
      };

      page.open('#{uri.to_s}', function() {
        page.render('#{directory}/#{user}-#{dom}.jpg');
        phantom.exit();
      });
  "

    Phantomjs.inline(js)


  end

  def fetch_url(uri, limit = 5)
    if limit == 0
      @log.warn "Too many HTTP redirects"
      return ''
    end

    response = Net::HTTP.get_response(uri)

    case response
    when Net::HTTPSuccess then
      response
    when Net::HTTPRedirection then
      location = response['location']
      @log.info "Redirected to #{location}"
      fetch_url(URI(location), limit - 1)
    else
      response.value
    end

  end

end



configfile = 'servers.yml'
config = YAML::load(File.open(configfile))

whm = WhmChecker.new(config[:config])

config[:servers].each do |server|
  whm.check_accounts(server[:host], server[:hash])
end
