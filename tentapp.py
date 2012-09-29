#!/usr/bin/env python

from __future__ import division
import os, time, random, sys, pprint
import string
import hmac, hashlib, base64
import json
import requests
import webbrowser
from urllib import urlencode
from colors import *

import myauthtokens
# myauthtokens should be a short file that looks like this:
#   mac_key_id = 'u:asdfasdfa'
#   mac_key = 'asdfasdfasdfasdfasdfasdfasdf'
# You can find these values by viewing the source of your profile page on tent.is


#-------------------------------------------------------------------------------------
#--- UTILS

def debugMain(s=''): print yellow('%s'%s)
def debugError(s=''): print red('ERROR: %s'%s)
def debugDetail(s=''): print cyan('    %s'%s)
def debugJson(s=''): print magenta(pprint.pformat(s))
def debugRequest(s=''): print green(' >> %s'%s)
def debugRaw(s=''): print white('>       '+s.replace('\n','\n>       '))

def randomString():
    return ''.join([random.choice(string.letters+string.digits) for x in xrange(20)])

def getHmacSha256AuthHeader(mac_key_id,mac_key,verb,resource,hostname,port,body=None):
    """Return an authentication header
    """
    debugMain('HMAC SHA 256')
    debugDetail('mac key id: %s'%repr(mac_key_id))
    debugDetail('mac key: %s'%repr(mac_key))
    timestamp = int(time.time())
    nonce = randomString()

    msgLines = []
    msgLines.append(str(timestamp))
    msgLines.append(nonce)
    msgLines.append(verb)
    msgLines.append(resource)
    msgLines.append(hostname)
    msgLines.append(str(port))
    if body:
        msgLines.append(body)
        msg = '\n'.join(msgLines) + '\n'
    else:
        msg = '\n'.join(msgLines) + '\n\n'

    debugDetail('input to hash: '+repr(msg))
    debugRaw(msg)

    if type(mac_key) == unicode: mac_key = mac_key.encode('utf8')
    if type(msg) == unicode: msg = msg.encode('utf8')

    digest = hmac.new(mac_key,msg,hashlib.sha256).digest()
    mac = base64.b64encode(digest).decode() # this produces unicode for some reason
    mac = mac.encode('utf8') # convert from unicode to string
    authHeader = 'MAC id="' + mac_key_id + '", '
    authHeader += 'ts="' + str(timestamp) + '", '
    authHeader += 'nonce="' + nonce + '", '
    authHeader += 'mac="' + mac + '"'
    debugDetail('auth header:')
    debugRaw(authHeader)
    if type(authHeader) == unicode: authHeader = authHeader.encode('utf8')
    return authHeader


#-------------------------------------------------------------------------------------
#--- APP

class TentApp(object):
    def __init__(self,serverDiscoveryUrl):
        debugMain('init: %s'%serverDiscoveryUrl)
        self.serverDiscoveryUrl = serverDiscoveryUrl
        self.hostname = serverDiscoveryUrl.replace('https://','').split('/')[0] # HACK
        self.apiRootUrls = []
        self.discoverAPIUrls(self.serverDiscoveryUrl)

        # details of this app
        # basic
        self.name = 'My Test App %s'%random.randint(11,99)
        self.description = 'description of my test app'

        # urls
        self.url = 'http://zzzzexample.com'
        self.icon = 'http://zzzzexample.com/icon.png'
        self.oauthCallbackUrl = 'http://zzzzexample.com/oauthcallback'
        self.postNotificationUrl = 'http://zzzzexample.com/notification'

        # permissions to request
        self.scopes = {
            'read_posts': 'x',
            'write_posts': 'x',
            'import_posts': 'x',
            'read_profile': 'x',
            'write_profile': 'x',
            'read_followers': 'x',
            'write_followers': 'x',
            'read_followings': 'x',
            'write_followings': 'x',
            'read_groups': 'x',
            'write_groups': 'x',
            'read_permissions': 'x',
            'write_permissions': 'x',
            'read_apps': 'x',
            'write_apps': 'x',
            'follow_ui': 'x',
            'read_secrets': 'x',
            'write_secrets': 'x',
        }
        self.profile_info_types = ['all']
        self.post_types = ['all']

        # auth stuff
        #  set by us
        self.state = None
        #  obtained from the server
        self.appID = None          # keep this.  these four come during registration

        self.mac_key_id = None     # temporary.  used during registration oauth flow
        self.mac_key = None        #
        self.mac_algorithm = None  #

        self.secret = None         # keep this.  a mac_key    that comes at the end of the oauth flow
        self.access_token = None   # keep this.  a mac_key_id that comes at the end of the oauth flow

    def discoverAPIUrls(self,serverDiscoveryUrl):
        """set self.apiRootUrls, return None
        """
        # get self.serverDiscoveryUrl doing just a HEAD request
        # look in HTTP header for Link: foo; rel="$REL_PROFILE"
        # TODO: if not, get whole page and look for <link href="foo" rel="$REL_PROFILE" />
        debugRequest('discovering: %s'%serverDiscoveryUrl)
        r = requests.head(url=serverDiscoveryUrl)

        # TODO: the requests api here only returns one link even when there are more than one in the
        # header.  I think it returns the last one, but we should be using the first one.
        self.apiRootUrls = [ r.links['https://tent.io/rels/profile']['url'] ]

        # remove trailing "/profile" from urls
        for ii in range(len(self.apiRootUrls)):
            self.apiRootUrls[ii] = self.apiRootUrls[ii].replace('/tent/profile','')

        debugDetail('server api urls = %s'%self.apiRootUrls)


    def _register(self):
        # get self.appID and self.mac_* from server
        # return none
        debugMain('registering...')

        # describe ourself to the server
        appInfoJson = {
            'name': self.name,
            'description': self.description,
            'url': self.url,
            'icon': 'http://example.com/icon.png',
            'redirect_uris': [self.oauthCallbackUrl],
            'scopes': self.scopes
        }
        debugJson(appInfoJson)

        headers = {
            'Content-Type': 'application/vnd.tent.v0+json',
            'Accept': 'application/vnd.tent.v0+json',
        }
        requestUrl = self.apiRootUrls[0] + '/apps'
        debugRequest('posting to %s'%requestUrl)
        r = requests.post(requestUrl, data=json.dumps(appInfoJson), headers=headers)

        # get oauth key in response
        debugDetail('headers from server:')
        debugJson(r.headers)
        debugDetail('json from server:')
        debugJson(r.json)
        if r.json is None:
            debugError('not json.  here is the actual body text:')
            debugRaw(r.text)
            return
        self.appID = r.json['id']
        self.mac_key_id = r.json['mac_key_id']
        self.mac_key = r.json['mac_key']
        self.mac_algorithm = r.json['mac_algorithm']
        debugDetail('registered successfully.  details:')
        debugDetail('  app id: %s'%repr(self.appID))
        debugDetail('  mac key: %s'%repr(self.mac_key))
        debugDetail('  mac key id: %s'%repr(self.mac_key_id))
        debugDetail('  mac algorithm: %s'%repr(self.mac_algorithm))

    def oauth_register(self):

        # first, register with the server to set
        #  self.appID and self.mac_*
        self._register()

        debugMain('oauth')

        # send user to the tent.is url to grant access
        # we will get the "code" in response
        self.state = randomString()
        params = {
            'client_id': self.appID,
            'redirect_uri': self.oauthCallbackUrl,
            'state': self.state,
            'scope': ','.join(self.scopes.keys()),
            'tent_profile_info_types': 'all',
            'tent_post_types': 'all',
            'tent_notification_url': self.postNotificationUrl,
        }
        requestUrl = self.apiRootUrls[0] + '/oauth/authorize'
        urlWithParams = requestUrl + '?' + urlencode(params)

        print '---------------------------------------------------------\\'
        print
        print 'Opening web browser so you can grant access on tent.is.'
        print
        print 'After you grant access, your browser will be redirected to'
        print 'a nonexistant page.  Look in the url and find the "code"'
        print 'parameter.  Paste it here:'
        print
        print 'Example:'
        print 'http://zzzzexample.com/oauthcallback?code=15673b7718651a4dd53dc7defc88759e&state=ahyKV...'
        print '                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^'
        print
        webbrowser.open(urlWithParams)
        code = raw_input('> ')
        print
        print '---------------------------------------------------------/'

        # trade the code for a permanent secret
        # first make the auth headers using the credentials from the registration step
        resource = '/tent/apps/%s/authorizations'%self.appID
        jsonPayload = {'code':code, 'token_type':'mac'}
        authHeader = getHmacSha256AuthHeader(mac_key_id = self.mac_key_id,
                                                mac_key = self.mac_key,
                                                verb = 'POST',
                                                resource = resource,
                                                hostname = self.hostname, # this includes the subdomain
                                                port = 443)

        # then construct and send the request
        print
        headers = {
            'Content-Type': 'application/vnd.tent.v0+json',
            'Accept': 'application/vnd.tent.v0+json',
            'Authorization': authHeader,
        }
        requestUrl = self.apiRootUrls[0] + resource
        debugRequest('posting to: %s'%requestUrl)
        r = requests.post(requestUrl, data=json.dumps(jsonPayload), headers=headers)

        # display our request
        debugDetail('request headers:')
        debugJson(r.request.headers)
        debugDetail('request data:')
        debugDetail(r.request.data)

        # then get the response
        print
        debugDetail('response headers:')
        debugJson(r.headers)
        debugDetail('response text:')
        debugRaw(r.text)
        if not r.json:
            print
            debugError('auth failed.')
            return
        debugJson(r.json)
        self.access_token = r.json['access_token']
        self.secret = r.json['mac_key']
        debugDetail('access token: %s'%self.access_token)
        debugDetail('secret: %s'%self.secret)

        # TODO: now we need to save the access token and secret to disk
        #  so we can use them in future requests to get actual work done


    def _genericGet(self,resource):
        requestUrl = self.apiRootUrls[0] + resource
        headers = {'Accept': 'application/vnd.tent.v0+json'}
        debugRequest(requestUrl)
        r = requests.get(requestUrl,headers=headers)
        if r.json is None:
            debugError('not json.  here is the actual body text:')
            debugRaw(r.text)
            return
        return r.json


    def getProfile(self):
        # this can happen without auth
        debugMain('getProfile')
        return self._genericGet('/profile')

    def putProfile(profileType,value):
        # PUT /profile/$profileType
        pass

    def follow(self,entityUrl):
        # POST /followings
        pass

    def getEntitiesIFollow(self,id=None):
        # GET /followings  [/$id]
        debugMain('getEntitiesIFollow')
        return self._genericGet('/followings')

    def unfollow(self,id):
        # DELETE /followings/$id
        pass

    def getFollowers(self,id=None):
        # GET /followers  [/$id]
        debugMain('getFollowers')
        return self._genericGet('/followers')

    def removeFollower(self,id):
        # DELETE /followers/$id
        pass

    def putPost(self,post,attachments=[]):
        debugMain('putPost')
        resource = '/tent/posts'
        requestUrl = self.apiRootUrls[0] + resource
        authHeader = getHmacSha256AuthHeader(mac_key_id = myauthtokens.mac_key_id, # HACK: use key from Tent Status app
                                                mac_key = myauthtokens.mac_key,
                                                verb = 'POST',
                                                resource = resource,
                                                hostname = self.hostname,
                                                port = 443)
        print
        headers = {
            'Content-Type': 'application/vnd.tent.v0+json',
            'Accept': 'application/vnd.tent.v0+json',
            'Authorization': authHeader,
        }
        debugRequest('posting to: %s'%requestUrl)
        r = requests.post(requestUrl, data=json.dumps(post), headers=headers)

        if r.json is None:
            debugDetail('request headers:')
            debugJson(r.request.headers)
            print
            debugDetail('request data:')
            debugRaw(r.request.data)
            print
            print yellow('  --  --  --  --  --')
            print
            debugDetail('response headers:')
            debugJson(r.headers)
            print
            debugDetail('response body:')
            debugRaw(r.text)
            print
            debugError('failed to put post.')
            print
        return r.json

    def getPosts(self,id=None):
        # GET /posts  [/$id]
        debugMain('getPosts')
        return self._genericGet('/posts')

    def getPostAttachment(self,id,filename):
        # GET /posts/$id/attachments/$filename
        pass


#-------------------------------------------------------------------------------------
#--- MAIN

if __name__ == '__main__':
    print yellow('-----------------------------------------------------------------------\\')

    username = myauthtokens.username
    url = 'https://%s.tent.is'%username

    app = TentApp(url) # this will also perform discovery on the url

    # try to post a status message using keys from myauthtokens
    post = {
        'type': 'https://tent.io/types/post/status/v0.1.0',
        'published_at': int(time.time()),
        'permissions': {
            'public': True,
        },
        'licenses': ['http://creativecommons.org/licenses/by/3.0/'],
        'content': {
            'text': 'Hello from Python!',
        }
    }
    app.putPost(post)

#     # Read various public things that don't require auth
#     profile = app.getProfile()
#     debugJson(profile)
#     followings = app.getEntitiesIFollow()
#     debugJson(followings)
#     followers = app.getFollowers()
#     debugJson(followers)
#     posts = app.getPosts()
#     debugJson(posts)

#     # Try to get new auth credentials
#     app.oauth_register()

    print yellow('-----------------------------------------------------------------------/')





