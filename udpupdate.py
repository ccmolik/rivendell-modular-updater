#!/usr/bin/python
#
# Courtesy of Chris Cmolik / WITR Radio <http://witr.rit.edu>

# Modular UDP Updater v1.0
#
# Copyright (c) 2010 Chris Cmolik / WITR Radio. All rights reserved.
# Redistribution and use in source and binary forms, with or without modification, are
# permitted provided that the following conditions are met:
# 
#    1. Redistributions of source code must retain the above copyright notice, this list of
#       conditions and the following disclaimer.
# 
#    2. Redistributions in binary form must reproduce the above copyright notice, this list
#       of conditions and the following disclaimer in the documentation and/or other materials
#       provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY CHRIS CMOLIK/WITR RADIO ``AS IS'' AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# The views and conclusions contained in the software and documentation are those of the
# authors and should not be interpreted as representing official policies, either expressed
# or implied, of Chris Cmolik/WITR Radio.

#
# Does what it says on the tin.
# 
# Usage: send a datagram (UDP Packet) containing "ARTIST --- SONG" to port 9999
# Substituting ARTIST with the artist and SONG with the song name
#
# Please note this expects to be able to read /var/local/dj.txt for 'static' text


### Imports ###
import syslog, telnetlib, time, httplib, telnetlib, urllib2
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from urllib import urlencode, urlopen
from xml.dom import minidom
## Config flags ##
# TODO: move into yaml file
##Globals - CHANGE THESE.##
UPDATE_LASTFM = False
# Icecast Admin URL
ICECAST_ADMIN_URL = 'http://your.icecast.server:8000/admin'
ICECAST_ADMIN_USER = 'admin'
ICECAST_ADMIN_PASSWORD = 'didyoureallythinkiwasgonnapostanadminpasswordhere?'
# FMB-80 RDS Username and Password
UPDATE_RDS = False
RDS_ENCODER_HOST = 'your-rds-server.or.ip.here'
RDS_ENCODER_USER = 'root'
RDS_ENCODER_PASSWORD = 'your-root-password'
DEFAULT_DURATION=500 # You may wish to tweak this. Only used for the RDS Encoder. 
UPDATE_EVERY = 5
# Update this with your Last.FM API key
API_KEY=''
SECRET=''
LFM_USER='your_lfm_user'
LFM_PASS='your_lfm_pass'
if UPDATE_LASTFM:
     import pylast	
     network = pylast.LastFMNetwork(api_key = API_KEY, api_secret=SECRET, username = LFM_USER, password_hash = pylast.md5(LFM_PASS))
# TuneIn Info
StationID="s00000"
PartnerId="partnerid"
PartnerKey="partnerKey"
# Whether or not to post to TuneIn
UPDATE_TUNEIN = False
# Delay
DELAY_SECONDS=0
### End globals ###
# Should only run if UPDATE_LASTFM is set to true
LAST_SONG=""
while ICECAST_ADMIN_URL[-1] == '/':
    ICECAST_ADMIN_URL = ICECAST_ADMIN_URL[:-1]
password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
password_mgr.add_password(None, ICECAST_ADMIN_URL,
    ICECAST_ADMIN_USER, ICECAST_ADMIN_PASSWORD)
handler = urllib2.HTTPBasicAuthHandler(password_mgr)
opener = urllib2.build_opener(handler)

def update_static(text):
    rds = telnetlib.Telnet(RDS_ENCODER_HOST)

    if 'User:' not in rds.read_until('User:', 5):
        raise Exception('Unable to log into RDS encoder: did not receive User prompt.')
    rds.write(RDS_ENCODER_USER + '\r\n')
    if 'Password:' not in rds.read_until('Password:', 5):
        raise Exception('Unable to log into RDS encoder: did not receive Password prompt.')
    rds.write(RDS_ENCODER_PASSWORD + '\r\n')

    # :-) is the string the RDS encoder gives. Cute, right?
    if ':-)\r\n'  not in rds.read_until(':-)\r\n', 5):
        raise Exception('Unable to log into RDS encoder: login failed.');
    sendRdsCommand(rds, 'PS_TEXT=%s' % text)
    sendRdsCommand(rds, 'RT_TEXT=%s' % text)
    syslog.syslog("Updated rds static with %s" % text)

def update_rds(artist, song):
    # Updates the RDS.
    rds = telnetlib.Telnet(RDS_ENCODER_HOST)
    if 'User:' not in rds.read_until('User:', 5):
        raise Exception('Unable to log into RDS encoder: did not receive User prompt.')
    rds.write(RDS_ENCODER_USER + '\r\n')
    if 'Password:' not in rds.read_until('Password:', 5):
        raise Exception('Unable to log into RDS encoder: did not receive Password prompt.')
    rds.write(RDS_ENCODER_PASSWORD + '\r\n')
    
    # :-) is the string the RDS encoder gives. Cute, right?
    if ':-)\r\n'  not in rds.read_until(':-)\r\n', 5):
        raise Exception('Unable to log into RDS encoder: login failed.');
    sendRdsCommand(rds, 'ARTISTNAME=%s' % artist)
    sendRdsCommand(rds, 'SONGTITLE=%s' % song)
    sendRdsCommand(rds, 'EXTRA=')
    sendRdsCommand(rds, 'DURATION=%d' % DEFAULT_DURATION)
    syslog.syslog("Updated RDS:%s - %s" % (artist, song))

def sendRdsCommand(conn, command):
    conn.write('%s\r\n' % command)
    match_index, matchobj, response = conn.expect(['^[+!]\r\n'], 5)
    response = response.rstrip()
    if response != '+':
        raise Exception('Failure response: %s' % response)

def update_icecast(song):
    global ICECAST_ADMIN_URL
    mounts_xml = opener.open(ICECAST_ADMIN_URL + '/listmounts')
    dom = minidom.parse(mounts_xml)             
    for source in dom.getElementsByTagName('source'):
        if ("BS_Extra_stream_you_dont_care_about" not in source.getAttribute('mount')):

            data = opener.open('%s/metadata?%s' %
                (ICECAST_ADMIN_URL,
                 urlencode((
                    ('mount', source.getAttribute('mount')),
                    ('mode', 'updinfo'),
                ('song', song),
                 ))))
    syslog.syslog("Updated icecast: %s" % song)

def post_tunein(artist, song):
    params = { 'partnerId': PartnerId, 'partnerKey': PartnerKey, 'id': StationID, 'title': song, 'artist': artist }
    response = urlopen("http://air.radiotime.com/Playing.ashx?%s" % urlencode(params)).read()
                
class UDPListener(DatagramProtocol):
    
    def datagramReceived(self, data, (host, port)):
        global network, LAST_SONG, UPDATE_RDS, UPDATE_LASTFM, UPDATE_TUNEIN
        syslog.syslog("received %r from %s:%d" % (data, host, port))
        stripdata = data.split()
        # This nasty bit actually seperates the song from the artist by the ---
        end_of_artist = 0
        done = False;
        artdone = False;
        ARTIST=''
        SONG=''
        GROUP=''
        end_of_song=0   
        for i in range(0,len(stripdata)-1):
            if stripdata[i] == "---":
                done = True
                end_of_artist = i
            if not done:
                ARTIST += " "
                ARTIST += stripdata[i]
        for j in range(end_of_artist + 1, len(stripdata)):
            if stripdata[j] == "::":
                artdone = True
                end_of_song = j;
            if not artdone:
                SONG += " "
                SONG += stripdata[j]
        GROUPlist=stripdata[end_of_song+1:]
        for item in GROUPlist:
            GROUP += item
        ARTIST=ARTIST[1:]
        SONG=SONG[1:]
        updateit = True
        if SONG == "" or ARTIST == "" or SONG == " " or ARTIST == " ":
	    # Customize /var/local/dj.txt to contain static text for when you're not displaying content
            file = open('/var/local/dj.txt', 'r')
            djname = file.read()
            file.close()
            update_icecast(djname) # Primarily for use when one is running a CD or other non-Rivendell content.
	    syslog.syslog("Attempting to update RDS with %s " % djname)
            update_static(djname)
            updateit = False    
        if((ARTIST + SONG) != LAST_SONG) and updateit:
            #Prioritizing our local stuff before remote updates
            # Sleep for a duration of time (for sync with content)
	    time.sleep(DELAY_SECONDS)
            LAST_SONG = ARTIST + SONG
            update_icecast(ARTIST + " - " + SONG)
            # Updating the RDS with the blank gives the default text.
            if UPDATE_RDS:
		update_rds(ARTIST, SONG)
            if UPDATE_LASTFM: 
            	network.scrobble(ARTIST, SONG, int(time.time()))
	    if UPDATE_TUNEIN:
            	post_tunein(ARTIST, SONG)
        
if __name__ == '__main__':
    syslog.syslog("RDS and Icecast UDP watcher started...")
    reactor.listenUDP(9999, UDPListener())
    reactor.run()
