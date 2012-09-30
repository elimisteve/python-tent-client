#!/usr/bin/env python

# This example will authenticate as an app with your server,
# fetch the recent posts from you and people you follow,
# and print them to the screen.

from __future__ import division
import pprint, time
import tentapp
from colors import *

print yellow('-----------------------------------------------------------------------\\')
print

app = tentapp.TentApp('https://rabbitwhiskers.tent.is')

app.oauthRegister()

# Because we've authenticated, getPosts() will get not only our own public posts
# but also those of people we follow and posts that mention us.
# tent.is limits this to the last 50 posts or so unless additional parameters are present
posts = app.getPosts()

# sort oldest first
posts.sort(key = lambda p: p['published_at'])

for post in posts:
    if post['type'] == 'https://tent.io/types/post/status/v0.1.0':
        timestamp = time.asctime(time.localtime(  post['published_at']  ))
        print '%s    %s'%(yellow(post['entity']), white(timestamp))
        print '    %s'%cyan(post['content']['text'])
        print

print yellow('-----------------------------------------------------------------------/')

