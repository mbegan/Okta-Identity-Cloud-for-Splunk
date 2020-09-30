
# encoding = utf-8

import os
import re
import sys
import time
import json
import logging
from datetime import datetime, timedelta

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

    #if less than 1 second left just be 1
    if mySecLeft < 1:
        helper.log_debug(log_metric + "_rateLimitEnforce mySecLeft was less than 1, setting to 1 to avoid issues")
        mySecLeft = 1

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

        # percentage to start throttling at
        try:
            warningpct = _getSetting(helper,'warning_threshold')
            warningpct = float(warningpct)
        except:
            warningpct=float(50.0)

        # Should we try to avoid warnings?
        try:
            avoidWarnings = _getSetting(helper,'avoid_warnings')
            avoidWarnings = bool(avoidWarnings)
        except:
            avoidWarnings=True

        #divide by zero is no good
        if myRemaining == 0:
            myRemaining = 1
        
        # figure out what our number of remaining calls is taking warning limits into account
        if avoidWarnings:
            helper.log_info(log_metric + "_rateLimitEnforce is applying a warning threshold adjustment " + str(myRemaining) + " before adjustment" )
            myRemaining = (myRemaining * warningpct / 100)
            if myRemaining < 1:
                myRemaining = 1
            helper.log_info(log_metric + "_rateLimitEnforce has applied the threshold adjustment " + str(myRemaining) + " after adjustment" )

        try:
            myPctLeft = float(100 * myRemaining / myLimit)
        except KeyError:
            myPctLeft = float(10.0)

        # How agressive do we throttle, less time to reset = more agressive sleep
        if mySecLeft * cps > myRemaining:
            sleepTime = mySecLeft * cps / myRemaining
        else:
            sleepTime = mySecLeft * cps / myRemaining / 10
 
        #never sleep much longer than reset time, saftey factor of 7 seconds
        if sleepTime > (mySecLeft + 7):
            sleepTime = mySecLeft + 7

        if myPctLeft < throttle:
            helper.log_info(log_metric + "_rateLimitEnforce is now pausing operations for " + str(sleepTime) + " to avoid exhausting the rate limit" )
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
        'max_log_batch': 60000,
        'user_limit': 200,
        'group_limit': 200,
        'app_limit': 500,
        'log_limit': 1000,
        'log_history': 7,
        'throttle_threshold': 25.0,
        'warning_threshold': 50.0,
        'http_request_timeout': 90,
        'fetch_empty_pages': False,
        'skip_empty_pages': True,
        'allow_proxy': False,
        'write_appUser': True,
        'write_groupUser': True,
        'bypass_verify_ssl_certs': False,
        'custom_ca_cert_bundle_path': False,
        'avoid_warnings': True
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

def _write_oktaResults(helper, ew, metric, results):
    global_account = helper.get_arg('global_account')
    okta_org = global_account['username']
    
    log_metric = "metric=" + metric + " | message="
    helper.log_debug(log_metric + "_write_oktaResults Invoked")
    
    eventHost = okta_org
    eventSourcetype = "OktaIM2:" + metric
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
        if 'log' == metric:
            eventTime = _fromIso8601ToUnix(item['published'])
        elif 'app' == metric:
            item.pop('_links','None')
        elif metric in ['user', 'group']:
            item.pop('_links','None')
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
    myValidPattern = ("https://" + okta_org + "/api/").lower()
    #settings
    try:
        max_log_batch = int(_getSetting(helper,'max_log_batch'))
    except:
        max_log_batch = int(60000)
    
    try:
        skipEmptyPages = bool(_getSetting(helper,'skip_empty_pages'))
    except:
        skipEmptyPages = bool(True)

    #if I get a full URL as resource use it, this will happne if we are picking up from a previous page
    if resource.lower().startswith(myValidPattern.lower()):
        url = resource
    else:
        url = "https://" + okta_org + "/api/v1" + resource
    
    url = url.lower()
    
    #make a first call
    response = _okta_client(helper, url, params, method)
    
    results = list()
    getPages = True
    stashNVal = str()
    #determine if and what the next pages is and retrieve as required
    while(getPages):
        n_val = str(response.pop('n_val', False))
        i_results = response.pop('results', {})
        i_count = int(len(i_results))
        results += i_results
        r_count = int(len(results))
        helper.log_debug(log_metric + "_okta_caller returned: " + str(i_count) + " this pass and: " + str(r_count) + " results so far")
        helper.log_debug(log_metric + "_okta_caller Iteration Count: " + str(i_count) + " Limit " + str(limit) )

        #special case here for 0 and logs
        if 0 == i_count:
            helper.log_debug(log_metric + "_okta_caller we have 0 results returned, determining what to store for next run" )
            getPages = False
            if "log" == opt_metric:
                if n_val.startswith(myValidPattern):
                    '''
                        429 case, penalty has been paid already but lets bail anyhow and pickup on next iteration
                        We will also encounter this case if/when the logs API ALWAYS returns a next link
                    '''
                    helper.log_info(log_metric + "_okta_caller n_val matches our valid pattern with 0 results, store the return n_val: " + n_val)
                    stashNVal = n_val                    
                else:
                    '''
                        The current functionality of the logs API will not return a next link if the request produced 0 results
                        in these cases we are going to keep asking for this same page until new logs are produced and we get a new cursor
                    '''
                    helper.log_info(log_metric + "_okta_caller n_val does not match our valid pattern with 0 results, store the current URL: " + url )
                    stashNVal = url
        elif i_count < limit:
            '''
                potential hitch here: If a limit value is raised after initial collection has begun 
                the number of results in each page will always be lower than our currently defined limit
                because limit is a retained parameter in our next link
                include something in the docs around this
            '''
            helper.log_debug(log_metric + "_okta_caller only returned " + str(i_count) + " results in this call, this indicates the next page is empty")
            if skipEmptyPages:
                helper.log_debug(log_metric + "_okta_caller skip empty pages is set to true")
                getPages = False
                if "log" == opt_metric:
                    helper.log_info(log_metric + "_okta_caller is will save the returned logs and store the n_val: " + n_val)
                    stashNVal = n_val
        if ( ("log" == opt_metric) and (r_count >= max_log_batch) ):
            '''
                To avoid exhausting the Splunk server we are going to end this thread after we hit our max batch size
                We will pick up on the next interval where we left off
            '''
            getPages = False
            helper.log_info(log_metric + "_okta_caller exceeded the max batch size for logs, saving returned logs and storing n_val: " + n_val)
            stashNVal = n_val

        if getPages:
            if n_val.startswith(myValidPattern):
                helper.log_info(log_metric + "_okta_caller we will be getting the next page: " + n_val)
                url = n_val
                response = _okta_client(helper, url, {}, method)
            else:
                helper.log_warning(log_metric + "_okta_caller n_val didn't match my pattern check: " + n_val)
                getPages = False
        elif "log" == opt_metric:
            if stashNVal.startswith(myValidPattern):
                helper.log_info(log_metric + "_okta_caller we will now stash n_val with: " + str(stashNVal) )
                helper.save_check_point((cp_prefix + "logs_n_val"), stashNVal)                
                helper.log_debug("n_val stashed")
            else:
                helper.log_warning(log_metric + "_okta_caller next link value was noneType " + str(stashNVal) )

    helper.log_debug("Returning Results from _okta_caller")
    return results

def _okta_client(helper, url, params, method):
    #Calls Okta
    #deals with rate limit enforcement before returning
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_okta_client Invoked with a url of: " + url)
    userAgent = "Splunk-AddOn/2.25.19"
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

    allow_proxy = bool(_getSetting(helper,'allow_proxy'))
    bypass_verify_ssl_certs = bool(_getSetting(helper,'bypass_verify_ssl_certs'))
    custom_ca_cert_bundle_path = _getSetting(helper,'custom_ca_cert_bundle_path')

    if bypass_verify_ssl_certs:
        sslVerify = False
    else:
        sslVerify = True
        
    helper.log_debug(log_metric + "_okta_client Invoked with sslVerify set to: " + str(sslVerify))

    #Requests uses the same verify param to use a custom bundle, if a custom bundle is defined verification is implied.
    if (custom_ca_cert_bundle_path):
        helper.log_debug(log_metric + "_okta_client Invoked with custom_ca_cert_bundle_path set to: " + str(custom_ca_cert_bundle_path))
        #if it is set, is the path valid?
        if os.path.exists(custom_ca_cert_bundle_path):
            #ok, override whatever bool param was set with this.
            helper.log_debug(log_metric + "_okta_client custom_ca_cert_bundle_path path is valid, overriding sslVerify")
            sslVerify = custom_ca_cert_bundle_path
        else:
            helper.log_debug(log_metric + "_okta_client custom_ca_cert_bundle_path path is NOT valid, ignoring")


    if allow_proxy:
        helper.log_info("Use of the proxy has been enabled through explicit definition of allow_proxy")
        response = helper.send_http_request \
           (
               url, method, parameters=params,
               payload=None, headers=headers,
               cookies=None, verify=sslVerify, cert=None,
               timeout=reqTimeout
            )
    else:
        helper.log_info("Use of a proxy has been explicitly disabled")
        response = helper.send_http_request \
           (
               url, method, parameters=params,
               payload=None, headers=headers,
               cookies=None, verify=sslVerify, cert=None,
               timeout=reqTimeout, use_proxy=False
            )

    # get the response headers
    r_headers = response.headers
    requestid = r_headers.pop('X-Okta-Request-Id','None')

    #try catch except
    try:
        results = response.json()
    except:
        sendBack = { 'results': {}, 'n_val': False }
        return sendBack
    
    if response.status_code == 429:
        helper.log_error(log_metric + "_okta_client returned an error: " + results['errorCode'] + " : " + results['errorSummary'] + " : rid=" + requestid)
        _rateLimitEnforce(helper, r_headers, response.status_code)
        # If we hit a 429 send back the current url as the n_val, we will pick up from there next time.
        sendBack = { 'results': {}, 'n_val': url }
        return sendBack
    
    helper.log_debug(log_metric + "_okta_client returned response to our request rid=" + requestid)
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
    helper.log_debug(log_metric + "_okta_client Returned: " + count + " records")
    if 'next' in response.links:
        n_val = response.links['next']['url']
        helper.log_info(log_metric + "_okta_client sees another page at this URL: " + n_val )
    else:
        n_val = False
        
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
    opt_limit = int(_getSetting(helper,'user_limit'))
    dtnow = datetime.now()
    end_date = dtnow.isoformat()[:-3] + 'Z'        
    start_date = helper.get_check_point((cp_prefix + "users_lastUpdated"))
    if ( (str(start_date)) == "None" ):
        start_date = "1970-01-01T00:00:00.000Z"
        
    helper.log_debug(log_metric + "_collectUsers Invoked, searching for users lastUpdated between " + start_date + " and " + end_date)

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
    
def _collectGroups(helper, ew):
    #Distinct entry point for group collection
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    global_account = helper.get_arg('global_account')
    cp_prefix = global_account['name']    
    resource = "/groups"
    method = "Get"        
    opt_limit = int(_getSetting(helper,'group_limit'))

    start_lastUpdated = helper.get_check_point((cp_prefix + "groups_lastUpdated"))
    if ( (str(start_lastUpdated)) == "None" ):
        start_lastUpdated = "1970-01-01T00:00:00.000Z"
        
    start_lastMembershipUpdated = helper.get_check_point((cp_prefix + "groups_lastMembershipUpdated"))
    if ( (str(start_lastMembershipUpdated)) == "None" ):
        start_lastMembershipUpdated = "1970-01-01T00:00:00.000Z"        
    
    lastUpdated = '(lastUpdated gt "' + start_lastUpdated + '")'
    lastMembershipUpdated = '(lastMembershipUpdated gt "' + start_lastMembershipUpdated + '")'
    
    helper.log_debug(log_metric + "_collectGroups Invoked, searching for groups lastUpdated after " + start_lastUpdated + 
     " or membershipUpdated after " + start_lastMembershipUpdated)

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
                group['_embedded']['stats'].pop('_links','None')
                if group['_embedded']['stats']['usersCount'] > 0:
                    members = _collectGroupUsers(helper, ew, group['id'])
                else:
                    members = []
                    
                if group['_embedded']['stats']['appsCount'] > 0:
                    assignedApps = _collectGroupApps(helper, group['id'])
                else:
                    assignedApps = []
            except KeyError:
                members = _collectGroupUsers(helper, ew, group['id'])
                assignedApps = _collectGroupApps(helper, group['id'])
            
            group['members'] = members    
            group['assignedApps'] = assignedApps
            '''    
            if group['_embedded']['stats']['groupPushMappingsCount'] > 0:
            '''
        
        helper.log_debug(log_metric + "_collectGroups checkpoint lastUpdated last guess is " + start_lastUpdated)
        helper.log_debug(log_metric + "_collectGroups checkpoint lastMembershipUpdated last guess is " + start_lastMembershipUpdated)
        helper.save_check_point((cp_prefix + "groups_lastUpdated"), start_lastUpdated)
        helper.save_check_point((cp_prefix + "groups_lastMembershipUpdated"), start_lastMembershipUpdated)
        
    return groups
    
def _collectGroupUsers(helper, ew, gid):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_collectGroupUsers has been invoked: " + gid )
    resource = "/groups/" + gid + "/skinny_users"
    method = "Get"
    write_groupUser = bool(_getSetting(helper,'write_groupUser'))
    '''
        concerned that this limit won't be honored in pagination links triggering the bug i fear
    '''
    opt_limit = int(_getSetting(helper,'group_limit'))
    params = {'limit': opt_limit}
    groupUsers = _okta_caller(helper, resource, params, method, opt_limit)
    
    myArray = []
    for groupUser in groupUsers:
        if write_groupUser:
            myArray.append( {"groupid": gid, "userid": groupUser['id']} )
        else:
            myArray.append(groupUser['id'])
            
    if write_groupUser:
        if ( len(myArray) > 0 ):
            helper.log_info(log_metric + "Writing " + (str(len(myArray))) + " groupUsers to splunk")
            _write_oktaResults(helper, ew, "groupUser", myArray)
            return ['see groupUser sourcetype']
        else:
            helper.log_info(log_metric + "Zero groupUsers returned")
            return []
    else:
        return myArray
    
def _collectGroupApps(helper, gid):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_collectGroupApps has been invoked for: " + gid )
    resource = "/groups/" + gid + "/apps"
    method = "Get"
    '''
        concerned that this limit won't be honored in pagination links triggering the bug i fear
    '''
    opt_limit = int(_getSetting(helper,'group_limit'))
    params = {'limit': opt_limit}
    groupApps = _okta_caller(helper, resource, params, method, opt_limit)
    
    assignedApps = []
    for groupApp in groupApps:
        assignedApps.append(groupApp['id'])
        
    return assignedApps
    
def _collectApps(helper, ew):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    
    helper.log_debug(log_metric + "_collectApps has been invoked")
    resource = "/apps"
    method = "Get"
    opt_limit = int(_getSetting(helper,'app_limit'))
    params = {'limit': opt_limit, 'filter': 'status eq "ACTIVE"'}
    apps = _okta_caller(helper, resource, params, method, opt_limit)
    
    for app in apps:
        #assigned_users
        assignedUsers = _collectAppUsers(helper, ew, app['id'])
        app['assigned_users'] = assignedUsers
        #assigned_groups
        assignedGroups = _collectAppGroups(helper, app['id'])
        app['assigned_groups'] = assignedGroups
        
    return apps
    
def _collectAppUsers(helper, ew, aid):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_collectAppUsers has been invoked: " + aid )
    resource = "/apps/" + aid + "/skinny_users"
    method = "Get"
    write_appUser = bool(_getSetting(helper,'write_appUser'))
    '''
        fear this limit won't be honored in pagination links triggering an early exit in _okta_caller
    '''
    opt_limit = int(_getSetting(helper,'app_limit'))
    params = {'limit': opt_limit}
    appUsers = _okta_caller(helper, resource, params, method, opt_limit)
    
    myArray = []
    for appUser in appUsers:
        if write_appUser:
            try:
                myUsername = appUser['credentials']['userName']
            except TypeError:
                myUsername = "UnDefined"

            myArray.append(
                {   "appid": aid,
                    "userid": appUser['id'],
                    "externalId": appUser['externalId'],
                    "userName": myUsername,
                    "created": appUser['created'],
                    "lastUpdated": appUser['lastUpdated'],
                    "statusChanged": appUser['statusChanged'],
                    "scope": appUser['scope'],
                    "status": appUser['status']
                })
        else:
            myArray.append(appUser['id'])
    
    if write_appUser:
        if ( len(myArray) > 0 ):
            helper.log_info(log_metric + "Writing " + (str(len(myArray))) + " appUsers to splunk")
            _write_oktaResults(helper, ew, "appUser", myArray)
            return ['see appUser sourcetype']
        else:
            helper.log_info(log_metric + "Zero appUsers returned")
            return []
    else:
        return myArray
    
def _collectAppGroups(helper, aid):
    opt_metric = helper.get_arg('metric')
    log_metric = "metric=" + opt_metric + " | message="
    helper.log_debug(log_metric + "_collectAppGroups has been invoked: " + aid )
    resource = "/apps/" + aid + "/groups"
    method = "Get"
    '''
        fear this limit won't be honored in pagination links triggering an early exit in _okta_caller
    '''
    opt_limit = int(_getSetting(helper,'app_limit'))
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

    since = helper.get_check_point((cp_prefix + "logs_since"))
    n_val = helper.get_check_point((cp_prefix + "logs_n_val"))
    
    if n_val:
        '''
            We are picking up a stashed next link, this is the normal operating mode
            define a blank param obj since the next link contains everythign we need
        '''
        helper.log_info(log_metric + "_collectLogs sees an existing next link value of: " + n_val + ", picking up from there" )
        resource = n_val
        params = {}
        helper.log_debug("deleting checkpoint")
        helper.delete_check_point((cp_prefix + "logs_n_val"))
        helper.log_debug("checkpoint deleted")
    elif since:        
        '''
            Not a cold start, use the checkpoint values for retrieval, this is a failsafe method
            This case should be uncommon and would usually be the indication of an error
        '''
        helper.log_info(log_metric + "_collectLogs sees an existing since value of: " + since + ", picking up from there" )
        params = {'sortOrder': 'ASCENDING', 'limit': opt_limit, 'since': since}

    else:
        '''
            this is a cold start, use our config values input for since
        '''
        opt_history = int(_getSetting(helper,'log_history'))
        helper.log_debug(log_metric + "_collectLogs sees a coldstart for logs, collecting " + (str(opt_history)) + " days of history" )
        dtsince = dtnow - timedelta( days = int(opt_history))
        since = dtsince.isoformat()[:-3] + 'Z'
        params = {'sortOrder': 'ASCENDING', 'limit': opt_limit, 'since': since}        

    helper.log_debug("Calling _okta_caller")
    logs = _okta_caller(helper, resource, params, method, opt_limit)
    helper.log_debug("_okta_caller returned")
    
    '''
        Stash the last UUID returned
        Stash the since value as a failsafe
        Remove potential dupes that may come from failsafe polling method
    '''
    if ( (len(logs)) > 0 ):
        lastUuid = helper.get_check_point((cp_prefix + "logs_lastUuid"))
        if (logs[0]['uuid'] == lastUuid):
            helper.log_debug(log_metric + "_collectLogs removing duplicate log uuid=" + lastUuid)
            pop = logs.pop(0)
            helper.log_info(log_metric + "_collectLogs removed duplicate entry: " + pop['uuid'])
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
    helper.log_debug(log_metric + "Fetching Metric")
    global_account = helper.get_arg('global_account')
    cp_prefix = global_account['name']    
    loglevel = helper.get_log_level()
    helper.set_log_level(loglevel)
    
    limits = { 'log':   {'minTime': 29,    'minSize':10, 'defSize':1000, 'maxSize': 1000, 'maxHistory': 180 }, 
               'user':  {'minTime': 899,   'minSize':20, 'defSize':200, 'maxSize': 1000 },
               'group': {'minTime': 899,   'minSize':20, 'defSize':500, 'maxSize': 1000 },
               'app':   {'minTime': 86390, 'minSize':20, 'defSize':500, 'maxSize': 1000 },
               'zset':  {'minTime': 86400, 'minSize':42, 'defSize':42,  'maxSize': 42  }, }
    
    #Enforce minTimes at runtime
    lastTs = helper.get_check_point((cp_prefix + ":" + opt_metric + ":lastRun"))
    if lastTs is None:
        lastTs = 0
    lastTs = int(lastTs)
    ts = int(time.time())
    diff = (ts - lastTs)
    
    #Confirm we aren't too frequent
    if (diff < limits[opt_metric]['minTime']):
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
        helper.log_debug(log_metric + "Invoking a call to reset all of our checkpoints")
        # can i run a query to find my checkpoints dynamically?
        # reset = helper.delete_check_point((cp_prefix + "logs_lastUuid"))
        # reset = helper.delete_check_point((cp_prefix + "logs_n_val"))
        # reset = helper.delete_check_point((cp_prefix + "logs_since"))
        # reset = helper.delete_check_point((cp_prefix + "users_lastUpdated"))
        # reset = helper.delete_check_point((cp_prefix + "groups_lastUpdated"))
        # reset = helper.delete_check_point((cp_prefix + ":log:lastRun"))
        # reset = helper.delete_check_point((cp_prefix + ":app:lastRun"))
        # reset = helper.delete_check_point((cp_prefix + ":group:lastRun"))
        # reset = helper.delete_check_point((cp_prefix + ":user:lastRun"))
    
    elif opt_metric == "log":
        helper.log_debug(log_metric + "Invoking a call for logs")
        logs = _collectLogs(helper)
        if ( len(logs) > 0 ):
            helper.log_info(log_metric + "Writing " + (str(len(logs))) + " logs to splunk")
            _write_oktaResults(helper, ew, opt_metric, logs)
        else:
            helper.log_info(log_metric + "Zero logs returned")
            
    elif opt_metric == "user":
        helper.log_debug(log_metric + "Invoking a call for users")
        users = _collectUsers(helper)
        
        if ( len(users) > 0 ):
            helper.log_debug(log_metric + "Writing " + (str(len(users))) + " users to splunk")
            _write_oktaResults(helper, ew, opt_metric, users)
        else:
            helper.log_debug(log_metric + "Zero users returned")
            
    elif opt_metric == "group":
        helper.log_debug(log_metric + "Invoking a call for groups")
        groups = _collectGroups(helper, ew)
        
        if ( len(groups) > 0 ):
            helper.log_info(log_metric + "Writing " + (str(len(groups))) + " groups to splunk")
            _write_oktaResults(helper, ew, opt_metric, groups)
        else:
            helper.log_info(log_metric + "Zero groups returned")
            
    elif opt_metric == "app":
        helper.log_debug(log_metric + "Invoking a call for apps")
        apps = _collectApps(helper, ew)
        
        if ( len(apps) > 0 ):
            helper.log_info(log_metric + "Writing " + (str(len(apps))) + " apps to splunk")
            _write_oktaResults(helper, ew, opt_metric , apps)
        else:
            helper.log_info(log_metric + "Zero apps returned")
            
    else:
        #this is bad
        helper.log_error(log_metric + "Something happened that should never have happend")

