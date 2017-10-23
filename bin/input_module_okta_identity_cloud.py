
# encoding = utf-8

import os
import re
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from solnlib.server_info import ServerInfo

'''
    IMPORTANT
    Edit only the validate_input and collect_events functions.
    Do not edit any other part in this file.
    This file is generated only once when creating the modular input.
'''

# For advanced users, if you want to create single instance mod input, uncomment this method.
'''
def use_single_instance_mode():
    return True
'''
def _fromIso8601ToUnix(iso8601):
    '''
    @@@ feels like a hack, revisit with fresh eyes
    '''
    date = datetime.strptime(iso8601, "%Y-%m-%dT%H:%M:%S.%fZ")
    unix = time.mktime(date.timetuple())
    myMS = float(iso8601[-5:-1])
    aTs = unix + myMS
    return aTs

def _rateLimitEnforce(helper, headers, rc):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="

    myTimeStamp = int(time.time())
    try:
        myReset = int(headers['X-Rate-Limit-Reset'])
        myRemaining = float(headers['X-Rate-Limit-Remaining'])
        myLimit = float(headers['X-Rate-Limit-Limit'])
        mySecLeft = int(myReset - myTimeStamp)
        myPctLeft = float(100 * myRemaining / myLimit)
    except KeyError:
        helper.log_info(log_metric + "_rateLimitEnforce with no ratelimit info in headers, using defaults")
        myRemaining = int(100)
        mySecLeft = int(60)
        myPctLeft = float(50.0)

    helper.log_debug(log_metric + "_rateLimitEnforce Invoked. There are " + str(mySecLeft) + " seconds left in the window and we have " + str(myPctLeft) + " percent of the limit available.  The response code returned was " + str(rc) )
    if rc == 429:
        #the rate limit is exhausted, sleep
        sleepTime = mySecLeft +7
        helper.log_warning(log_metric + "_rateLimitEnforce is now pausing operations for " + str(sleepTime) + " as the rate limit has been exhausted" )
        time.sleep(sleepTime)
    elif 200 <= rc <= 299:
        #sleep only if rate limit reaches a rate, adapt based on exhaustion and time left
        # how many calls per second do we assume are happening
        cps=4
        # percentage to start throttling at

        try:
            throttle = _getSetting(helper,'throttle_threshold')
            throttle = float(throttle)
        except:
            throttle=float(20.0)

        #divide by zero is no good
        if myRemaining == 0:
            myRemaining = 1

        # How agressive do we throttle, less time to reset = more agressive sleep
        if mySecLeft * cps > myRemaining:
            sleepTime = mySecLeft * cps / myRemaining
        else:
            sleepTime = mySecLeft * cps / myRemaining / 100
 
        #never sleep much longer than reset time, saftey factor of 7 seconds
        if sleepTime > (mySecLeft + 7):
            sleepTime = mySecLeft + 7

        if myPctLeft < throttle:
            helper.log_warning(log_metric + "_rateLimitEnforce is now pausing operations for " + str(sleepTime) + " to avoid exhausting the rate limit" )
            time.sleep(sleepTime)
            
    elif 400 <= rc <= 499:
        #some error on the client side, throw in a sleep to keep from hammering us but nothing adaptive
        helper.log_warning(log_metric + "_rateLimitEnforce is going to pause for 1 second now as a client side error was returned from the server (400-499)" )
        time.sleep(1)
    elif rc >= 500:
        helper.log_error(log_metric + "_rateLimitEnforce is going to pause for 1 second now as a client server side error was indicated (500+)" )
        time.sleep(1)
    else:
        helper.log_error(log_metric + "_rateLimitEnforce is going to pause for 1 second now as an unknown error was indicated (not an http response code)" )
        time.sleep(1)

def _getSetting(helper, setting):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_getSetting Invoked")
    myDefaults = {
        'max_log_batch': 6000,
        'user_limit': 200,
        'group_limit': 200,
        'app_limit': 200,
        'log_limit': 100,
        'log_history': 7,
        'throttle_threshold': 25.0,
        'http_request_timeout': 90,
        'fetch_empty_pages': False,
        'use_now_for_until': True,
        'skip_empty_pages': True
    }

    # early fail if the setting we've been asked for isn't something we know about
    if setting not in myDefaults:
        helper.log_error(log_metric + "_getSetting has no way of finding values for: " + str(setting))
        return None
    else:
        helper.log_info(log_metric + "_getSetting is looking for values for: " + str(setting))

    try:
        myVal = helper.get_global_setting(setting)
        helper.log_debug(log_metric + "_getSetting has a defined " + setting + " value of: " + str(myVal))
    except:
        myVal = myDefaults[setting]
        helper.log_debug(log_metric + "_getSetting has a default1 " + setting + " value of: " + str(myVal))
    
    #test for nonetype
    if myVal is None:
        myVal = myDefaults[setting]
        helper.log_debug(log_metric + "_getSetting has a default2 " + setting + " value of: " + str(myVal))

    return myVal

def _write_oktaResults(helper, ew, results):
    global_account = helper.get_arg('global_account')
    okta_org = global_account['username']
    
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_write_oktaResults Invoked")
    
    eventHost = okta_org
    eventSourcetype = "OktaIM2:" + opt_metric
    eventSource = "Okta:im2"
    eventTime = None
    for item in results:
        #print log
        '''
            extract the time
                log.published
                user.lastUpdated
                group.lastUpdated
                app.lastUpdated
            derive the host
                okta_org
        '''
        if 'log' == opt_metric:
            eventTime = _fromIso8601ToUnix(item['published'])
        elif 'app' == opt_metric:
            pop = item.pop('_links','None')
        elif opt_metric in ['user', 'group']:
            pop = item.pop('_links','None')
            eventTime = _fromIso8601ToUnix(item['lastUpdated'])
            
        data = json.dumps(item)
        data = re.sub(r'[\s\r\n]+'," ", data)
        event = helper.new_event \
        (
            source=eventSource,
            index=helper.get_output_index(),
            sourcetype=eventSourcetype,
            data=data,
            host=eventHost,
            time=eventTime
        )
        ew.write_event(event)

def _okta_caller(helper, resource, params, method, limit):
    #this calls the _okta_client with baked URL's
    #makes pagination calls
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_okta_caller Invoked")

    global_account = helper.get_arg('global_account')
    cp_prefix = global_account['name']
    okta_org = global_account['username']
    myValidPattern = ("https://" + okta_org + "/api/")

    #if I get a full URL as resource use it
    if resource.startswith(myValidPattern):
        url = resource
    else:
        url = "https://" + okta_org + "/api/v1" + resource

    response = _okta_client(helper, url, params, method)
    n_val = str(response.pop('n_val', None))
    results = response.pop('results', {})
    i_count = int(len(results))

    if ( ("log" == opt_metric) and (0 == i_count) ):
        if n_val is None:
            #store the current URL, we may be dealing with a slow org
            helper.log_info(log_metric + "_okta_caller n_val was NoneType with 0 results, store current URL as n_val: " + url )
            helper.save_check_point((cp_prefix + "logs_n_val"), url)
        else:
            #store the value of n_val, might be a 429 case
            helper.log_info(log_metric + "_okta_caller n_val was Defined with 0 results, probably 429 store n_val: " + n_val)
            helper.save_check_point((cp_prefix + "logs_n_val"), n_val)
        
    '''
        if logs stash the results after max_log_batch is hit to avoid memory exhastion on collector
        For other endpoints page and return when complete... (no good way to page and continue)
    '''
    try:
        max_log_batch = int(_getSetting(helper,'max_log_batch'))
    except:
        max_log_batch = int(6000)
    
    try:
        skipEmptyPages = bool(_getSetting(helper,'skip_empty_pages'))
    except:
        skipEmptyPages = bool(True)

    myCon = True
    while ((n_val.startswith(myValidPattern)) and (myCon)):
        helper.log_debug(log_metric + "_okta_caller fetching next page: " + n_val)
        url = n_val
        response = _okta_client(helper, url, {}, method)
        n_val = str(response.pop('n_val', None))
        i_res = response.pop('results', {})
        results += i_res
        i_count = int(len(i_res))
        r_count = int(len(results))
        helper.log_debug(log_metric + "_okta_caller has returned " + (str(r_count)) + " results so far, fetching next page: " + n_val)
        if ( (opt_metric == "log") and ( r_count >= max_log_batch) ): 
            helper.log_info(log_metric + "_okta_caller exceeded the max batch size for logs, stashing returned results and n_val of " + n_val)
            helper.save_check_point((cp_prefix + "logs_n_val"), n_val)
            myCon = False
        # If this iterations retrieve value is lower than the limit
        # we can be sure we are at the end of the result
        if i_count < limit:
            helper.log_info(log_metric + "_okta_caller only returned " + (str(i_count)) + " results in this call, this indicates an empty next page: " + n_val)
            # if skipEmptyPages is set we can just skip fetching that page
            if skipEmptyPages:
                helper.log_info(log_metric + "_okta_caller has collected all available data, since skipEmptyPages is true we'll not be collecting " + n_val + " at this time")
                myCon = False
                if (opt_metric == "log"):
                    helper.log_info(log_metric + "_okta_caller is stashing returned results and n_val of " + n_val)
                    if n_val is None:
                        helper.log_info(log_metric + "_okta_caller n_val was NoneType so we aren't stashing")
                    else:
                        helper.save_check_point((cp_prefix + "logs_n_val"), n_val)
            
    return results

def _okta_client(helper, url, params, method):
    #Calls Okta
    #deals with rate limit enforcement before returning
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_okta_client Invoked with a url of: " + url)
    userAgent = "Splunk-AddOn/2.0b"
    global_account = helper.get_arg('global_account')
    okta_token = global_account['password']    
    
    try:
        reqTimeout = float(_getSetting(helper,'http_request_timeout'))
    except:
        helper.log_debug(log_metric + "_okta_client using coded timeout value")
        reqTimeout = float(90)

    headers = { 'Authorization': 'SSWS ' + okta_token, 
                'User-Agent': userAgent, 
                'Content-Type': 'application/json', 
                'accept': 'application/json' }
                
    if ServerInfo.is_cloud_instance:
        helper.log_debug("This is a cloud instance, disable use of proxy")
        response = helper.send_http_request \
           (
               url, method, parameters=params, 
               payload=None, headers=headers,
               cookies=None, verify=True, cert=None,
               timeout=reqTimeout, use_proxy=False
            )
    else:
        helper.log_debug("This is NOT cloud instance, allow use of proxy if configured")
        response = helper.send_http_request \
           (
               url, method, parameters=params, 
               payload=None, headers=headers,
               cookies=None, verify=True, cert=None,
               timeout=reqTimeout
            )

    # get the response headers
    r_headers = response.headers
    requestid = r_headers.pop('X-Okta-Request-Id','None')
    
    #try catch except
    try:
        results = response.json()
    except:
        sendBack = { 'results': {}, 'n_val': None }
        return sendBack
    
    if response.status_code == 429:
        helper.log_error(log_metric + " _okta_client returned an error: " + results['errorCode'] + " : " + results['errorSummary'] + " : requestid : " + requestid)
        _rateLimitEnforce(helper, r_headers, response.status_code)
        # If we hit a 429 send back the current url as the n_val, we will pick up from there next time.
        sendBack = { 'results': {}, 'n_val': url }
        return sendBack
    
    helper.log_debug(log_metric + "_okta_client returned response to requestid : " + requestid)
    #historical_responses = response.history
    # get response status code
    #r_status = response.status_code
    # check the response status, if the status is not sucessful, raise requests.HTTPError
    response.raise_for_status()
    # get the response body as text
    #r_text = response.text
    # get response body as json. If the body text is not a json string, raise a ValueError
    #r_json = response.json()
    
    _rateLimitEnforce(helper, r_headers, response.status_code)
    count = str(len(results))
    helper.log_debug(log_metric + " _okta_client Returned: " + count + " records")
    if 'next' in response.links:
        n_val = response.links['next']['url']
        helper.log_info(log_metric + "_okta_client sees another page at this URL: " + n_val )
    else:
        n_val = None
        
    sendBack = { 'results': results, 'n_val': n_val }
    return sendBack
    
def _collectUsers(helper):
    #Distinct entry point for user collection
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    global_account = helper.get_arg('global_account')
    cp_prefix = global_account['name']
    resource = "/users"
    method = "Get"
    opt_limit = int(helper.get_arg('limit'))
    dtnow = datetime.now()
    end_date = dtnow.isoformat()[:-3] + 'Z'        
    start_date = helper.get_check_point((cp_prefix + "users_lastUpdated"))
    if ( (str(start_date)) == "None" ):
        start_date = "1970-01-01T00:00:00.000Z"
        
    helper.log_debug(log_metric + " _collectUsers Invoked, searching for users lastUpdated between " + start_date + " and " + end_date)

    myfilter = 'lastUpdated gt "' + start_date + '" and lastUpdated lt "' + end_date + '"'
    params = {'filter': myfilter, 'limit': opt_limit}
    users = _okta_caller(helper, resource, params, method, opt_limit)

    if ( len(users) > 0 ):
        lastUpdated = _fromIso8601ToUnix(users[-1]['lastUpdated'])
        end_date = users[-1]['lastUpdated']
        helper.log_debug(log_metric + "_collectUsers checkpoint lastUpdated first guess is " + end_date)
        #loop through users returned and determine the largest lastUpdated date
        for user in users:
            t_lastUpdated = _fromIso8601ToUnix(user['lastUpdated'])
            if t_lastUpdated > lastUpdated:
                lastUpdated = t_lastUpdated
                end_date = user['lastUpdated']
                helper.log_debug(log_metric + "_collectUsers checkpoint lastUpdated middle guess is " + end_date)
                
        #stash the value of our current end_date, will be used as start date on next run
        helper.log_debug(log_metric + "_collectUsers checkpoint lastUpdated last guess is " + end_date)
        helper.save_check_point((cp_prefix + "users_lastUpdated"), end_date)
            
    return users
    
def _collectGroups(helper):
    #Distinct entry point for group collection
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    global_account = helper.get_arg('global_account')
    cp_prefix = global_account['name']    
    resource = "/groups"
    method = "Get"        
    opt_limit = int(helper.get_arg('limit'))
    dtnow = datetime.now()
    end_date = dtnow.isoformat()[:-3] + 'Z'
    start_lastUpdated = helper.get_check_point((cp_prefix + "groups_lastUpdated"))
    if ( (str(start_lastUpdated)) == "None" ):
        start_lastUpdated = "1970-01-01T00:00:00.000Z"
        
    start_lastMembershipUpdated = helper.get_check_point((cp_prefix + "groups_lastMembershipUpdated"))
    if ( (str(start_lastMembershipUpdated)) == "None" ):
        start_lastMembershipUpdated = "1970-01-01T00:00:00.000Z"        
    
    lastUpdated = '( (lastUpdated gt "' + start_lastUpdated + '") and (lastUpdated lt "' + end_date + '") )'
    lastMembershipUpdated = '( (lastMembershipUpdated gt "' + start_lastMembershipUpdated + '") and (lastMembershipUpdated lt "' + end_date + '") )'
    
    helper.log_debug(log_metric + " _collectGroups Invoked, searching for groups lastUpdated between " + start_lastUpdated + 
     " and " + end_date + " or membershipUpdated between " + start_lastMembershipUpdated + " and " + end_date)
    myfilter = "( " + lastUpdated + " or " + lastMembershipUpdated + " )"
    params = {'filter': myfilter, 'limit': opt_limit, 'expand': 'stats,app'}
    groups = _okta_caller(helper, resource, params, method, opt_limit)
        
    if ( len(groups) > 0 ):
        lastUpdated = _fromIso8601ToUnix(start_lastUpdated)
        lastMembershipUpdated = _fromIso8601ToUnix(start_lastMembershipUpdated)
        
        helper.log_debug(log_metric + "_collectGroups checkpoint lastUpdated first guess is " + start_lastUpdated)
        helper.log_debug(log_metric + "_collectGroups checkpoint lastMembershipUpdated first guess is " + start_lastMembershipUpdated)
        #loop to find the most recent date from result set
        for group in groups:
            t_lastUpdated = _fromIso8601ToUnix(group['lastUpdated'])
            if t_lastUpdated > lastUpdated:
                lastUpdated = t_lastUpdated
                start_lastUpdated = group['lastUpdated']
                helper.log_debug(log_metric + "_collectGroups checkpoint lastUpdated middle guess is " + start_lastUpdated)
                
            t_lastMembershipUpdated = _fromIso8601ToUnix(group['lastMembershipUpdated'])
            if t_lastMembershipUpdated > lastMembershipUpdated:
                lastMembershipUpdated = t_lastMembershipUpdated
                start_lastMembershipUpdated = group['lastMembershipUpdated']
                helper.log_debug(log_metric + "_collectGroups checkpoint lastMembershipUpdated middle guess is " + start_lastMembershipUpdated)
        
        #Loop through and enrich groups with members IF they have members or apps assigned    
        for group in groups:
            #pop the _links object, it is pointless in this context
            try:
                pop = group['_embedded']['stats'].pop('_links','None')
                if group['_embedded']['stats']['usersCount'] > 0:
                    members = _collectGroupUsers(helper, group['id'])
                else:
                    members = []
                    
                if group['_embedded']['stats']['appsCount'] > 0:
                    assignedApps = _collectGroupApps(helper, group['id'])
                else:
                    assignedApps = []
            except KeyError:
                members = _collectGroupUsers(helper, group['id'])
                assignedApps = _collectGroupApps(helper, group['id'])
            
            group['members'] = members    
            group['assignedApps'] = assignedApps
            '''    
            if group['_embedded']['stats']['groupPushMappingsCount'] > 0:
            '''
        
        helper.log_debug(log_metric + " _collectGroups checkpoint lastUpdated last guess is " + start_lastUpdated)
        helper.log_debug(log_metric + " _collectGroups checkpoint lastMembershipUpdated last guess is " + start_lastMembershipUpdated)
        helper.save_check_point((cp_prefix + "groups_lastUpdated"), start_lastUpdated)
        helper.save_check_point((cp_prefix + "groups_lastMembershipUpdated"), start_lastMembershipUpdated)
        
    return groups
    
def _collectGroupUsers(helper, gid):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_collectGroupUsers has been invoked: " + gid )
    resource = "/groups/" + gid + "/skinny_users"
    method = "Get"
    opt_limit = int(helper.get_arg('limit'))
    params = {'limit': opt_limit}
    groupUsers = _okta_caller(helper, resource, params, method, opt_limit)
    
    members = []
    for groupUser in groupUsers:
        members.append(groupUser['id'])
        
    return members
    
def _collectGroupApps(helper, gid):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + " _collectGroupApps has been invoked for: " + gid )
    resource = "/groups/" + gid + "/apps"
    method = "Get"
    opt_limit = int(helper.get_arg('limit'))
    params = {'limit': opt_limit}
    groupApps = _okta_caller(helper, resource, params, method, opt_limit)
    
    assignedApps = []
    for groupApp in groupApps:
        assignedApps.append(groupApp['id'])
        
    return assignedApps
    
def _collectApps(helper):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    
    helper.log_debug(log_metric + "_collectApps has been invoked")
    opt_limit = int(helper.get_arg('limit'))
    resource = "/apps"
    method = "Get"
    opt_limit = int(helper.get_arg('limit'))
    params = {'limit': opt_limit, 'filter': 'status eq "ACTIVE"'}
    apps = _okta_caller(helper, resource, params, method)
    
    for app in apps:
        #assigned_users
        assignedUsers = _collectAppUsers(helper, app['id'])
        app['assigned_users'] = assignedUsers
        #assigned_groups
        assignedGroups = _collectAppGroups(helper, app['id'])
        app['assigned_groups'] = assignedGroups
        
    return apps
    
def _collectAppUsers(helper, aid):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_collectAppUsers has been invoked: " + aid )
    resource = "/apps/" + aid + "/skinny_users"
    method = "Get"
    opt_limit = int(helper.get_arg('limit'))
    params = {'limit': opt_limit}
    appUsers = _okta_caller(helper, resource, params, method, opt_limit)
    
    assigned_users = []
    for appUser in appUsers:
        assigned_users.append(appUser['id'])
        
    return assigned_users
    
def _collectAppGroups(helper, aid):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_collectAppGroups has been invoked: " + aid )
    resource = "/apps/" + aid + "/groups"
    method = "Get"
    opt_limit = int(int(helper.get_arg('limit')))
    params = {'limit': opt_limit}
    appGroups = _okta_caller(helper, resource, params, method, opt_limit)
    
    assigned_groups = []
    for appGroup in appGroups:
        assigned_groups.append(appGroup['id'])
        
    return assigned_groups
    
def _collectLogs(helper):
    #Distinct entry point for log Collection
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_collectLogs Invoked")
    global_account = helper.get_arg('global_account')
    cp_prefix = global_account['name']
    resource = "/logs"
    method = "Get"    
    dtnow = datetime.now()

    opt_limit = int(_getSetting(helper,'log_limit'))
    opt_history = int(_getSetting(helper,'log_history'))

    if (_getSetting(helper,'use_now_for_until')):
        until = 'now'
    else:
        until = dtnow.isoformat()[:-3] + 'Z'

    since = helper.get_check_point((cp_prefix + "logs_since"))
    n_val = helper.get_check_point((cp_prefix + "logs_n_val"))
    
    if n_val:
        #We are picking up a stashed next link (meaning we exited a large batch midstream)
        helper.log_debug(log_metric + "_collectLogs sees an existing next link value of: " + n_val + ", picking up from there." )
        resource = n_val
        #params are all in the next link
        params = {}
        #delete it so we don't pick it up again
        helper.delete_check_point((cp_prefix + "logs_n_val"))
    elif since:        
        #Not a cold start, use the checkpoint values for retrieval
        helper.log_debug(log_metric + "_collectLogs sees an existing since value of: " + since + ", picking up from there." )
        params = {'sortOrder': 'ASCENDING', 'limit': opt_limit, 'since': since, 'until': until}
    else:
        #this is a cold start, use our config input for since
        helper.log_debug(log_metric + "_collectLogs sees a coldstart for logs, collecting " + (str(opt_history)) + " days of history." )
        dtsince = dtnow - timedelta( days = int(opt_history))
        since = dtsince.isoformat()[:-3] + 'Z'
        params = {'sortOrder': 'ASCENDING', 'limit': opt_limit, 'since': since, 'until': until}        

    logs = _okta_caller(helper, resource, params, method, opt_limit)
    
    # stash the last UUID and a since value as a failsafe.
    # Also remove dupes potentially triggered in this failsafe mode
    lastUuid = helper.get_check_point((cp_prefix + "logs_lastUuid"))
    if ( (len(logs)) > 0 ):
        if (logs[0]['uuid'] == lastUuid):
            helper.log_debug(log_metric + "_collectLogs removing duplicate entry: " + pop['uuid'])
            pop = logs.pop(0)    
        helper.log_debug(log_metric + "_collectLogs checkpoint logs_since: " + logs[-1]['published'] + " and logs_lastUuid: " + logs[-1]['uuid'])
        helper.save_check_point((cp_prefix + "logs_since"), logs[-1]['published'])
        helper.save_check_point((cp_prefix + "logs_lastUuid"), logs[-1]['uuid'])
        
    return logs
    
def validate_input(helper, definition):
    """Implement your own validation logic to validate the input stanza configurations"""
    # Best i can tell this never gets invoked
    helper.log_debug("validate_input has been invoked" )
    
    pass

def collect_events(helper, ew):
    """ Do this thing """
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "Fetching Metric.")
    global_account = helper.get_arg('global_account')
    cp_prefix = global_account['name']    
    loglevel = helper.get_log_level()
    helper.set_log_level(loglevel)
    
    limits = { 'log':   {'minTime': 30,    'minSize':10, 'defSize':100, 'maxSize': 100, 'maxHistory': 180 }, 
               'user':  {'minTime': 3590,  'minSize':20, 'defSize':200, 'maxSize': 300 },
               'group': {'minTime': 3590,  'minSize':20, 'defSize':200, 'maxSize': 300 },
               'app':   {'minTime': 86390, 'minSize':20, 'defSize':200, 'maxSize': 300 },
               'zset':  {'minTime': 86400, 'minSize':42, 'defSize':42, 'maxSize': 42  }, }
    
    #Enforce minTimes at runtime
    lastTs = helper.get_check_point((cp_prefix + ":" + opt_metric + ":lastRun"))
    if lastTs is None:
        lastTs = 0
    lastTs = int(lastTs)
    ts = int(time.time())
    diff = (ts - lastTs)
    
    #Confirm we aren't too frequent
    if (diff <= limits[opt_metric]['minTime']):
        helper.log_error(log_metric + "collect_events Invoked, it has been only been " + str(diff) + " seconds since we last ran, skipping")
        return
    
    #Confirm are values are within an acceptable range

    try:
        #limVar becomes log_limit, user_limit etc
        limVar = opt_metric + '_limit'
        opt_limit = _getSetting(helper, limVar )
        opt_limit = int(opt_limit)
    except:
        opt_limit = limits[opt_metric]['defSize']
        
    if (limits[opt_metric]['minSize'] <= opt_limit <= limits[opt_metric]['maxSize']):
        helper.log_debug(log_metric + "collect_events Invoked, the input limit size of " + str(opt_limit) + " is INSIDE the allowable range, continuing")
    else:
        helper.log_error(log_metric + "collect_events Invoked, the input limit size of " + str(opt_limit) + " is OUTSIDE the allowable range of " + str(limits[opt_metric]['minSize']) + " and " + str(limits[opt_metric]['maxSize']) + ", skipping")
        return
    
    #passed validation, set the lastrun checkpoint
    helper.save_check_point((cp_prefix + ":" + opt_metric + ":lastRun"), diff)
    
    if opt_metric == "zset":
        helper.log_debug(log_metric + "Invoking a call to reset checkpoints for logs, users and groups.")
        reset = helper.delete_check_point((cp_prefix + "logs_lastUuid"))
        reset = helper.delete_check_point((cp_prefix + "users_lastUpdated"))
        reset = helper.delete_check_point((cp_prefix + "groups_lastUpdated"))
        reset = helper.delete_check_point((cp_prefix + ":log:lastRun"))
        reset = helper.delete_check_point((cp_prefix + ":app:lastRun"))
        reset = helper.delete_check_point((cp_prefix + ":group:lastRun"))
        reset = helper.delete_check_point((cp_prefix + ":user:lastRun"))
    
    elif opt_metric == "log":
        '''
        reset = helper.delete_check_point((cp_prefix + "logs_lastUuid"))
        reset = helper.delete_check_point((cp_prefix + "logs_since"))
        reset = helper.delete_check_point((cp_prefix + "logs_n_val"))
        '''
        
        helper.log_debug(log_metric + "Invoking a call for logs.")
        logs = _collectLogs(helper)
        if ( len(logs) > 0 ):
            helper.log_debug(log_metric + "Writing " + (str(len(logs))) + " logs to splunk.")
            _write_oktaResults(helper, ew, logs)
        else:
            helper.log_debug(log_metric + "Zero logs returned...")
            
    elif opt_metric == "user":
        #reset = helper.delete_check_point((cp_prefix + "users_lastUpdated"))
        helper.log_debug(log_metric + "Invoking a call for users.")
        users = _collectUsers(helper)
        
        if ( len(users) > 0 ):
            helper.log_debug(log_metric + "Writing " + (str(len(users))) + " users to splunk.")
            _write_oktaResults(helper, ew, users)
        else:
            helper.log_debug(log_metric + "Zero users returned...")
            
    elif opt_metric == "group":
        #reset = helper.delete_check_point((cp_prefix + "groups_lastUpdated"))
        helper.log_debug(log_metric + "Invoking a call for groups.")
        groups = _collectGroups(helper)
        
        if ( len(groups) > 0 ):
            helper.log_debug(log_metric + "Writing " + (str(len(groups))) + " groups to splunk.")
            _write_oktaResults(helper, ew, groups)
        else:
            helper.log_debug(log_metric + "Zero groups returned...")
            
    elif opt_metric == "app":
        helper.log_debug(log_metric + "Invoking a call for apps.")
        apps = _collectApps(helper)
        
        if ( len(apps) > 0 ):
            helper.log_debug(log_metric + "Writing " + (str(len(apps))) + " apps to splunk.")
            _write_oktaResults(helper, ew, apps)
        else:
            helper.log_debug(log_metric + "Zero apps returned...")
            
    else:
        #this is bad
        return "fail"
