
# encoding = utf-8

def process_event(helper, *args, **kwargs):
    """
    # IMPORTANT
    # Do not remove the anchor macro:start and macro:end lines.
    # These lines are used to generate sample code. If they are
    # removed, the sample code will not be updated when configurations
    # are updated.

    [sample_code_macro:start]

    # The following example gets and sets the log level
    helper.set_log_level(helper.log_level)

    # The following example gets account information
    user_account = helper.get_user_credential("<account_name>")

    # The following example sends rest requests to some endpoint
    # response is a response object in python requests library
    response = helper.send_http_request("http://www.splunk.com", "GET", parameters=None,
                                        payload=None, headers=None, cookies=None, verify=True, cert=None, timeout=None, use_proxy=True)
    # get the response headers
    r_headers = response.headers
    # get the response body as text
    r_text = response.text
    # get response body as json. If the body text is not a json string, raise a ValueError
    r_json = response.json()
    # get response cookies
    r_cookies = response.cookies
    # get redirect history
    historical_responses = response.history
    # get response status code
    r_status = response.status_code
    # check the response status, if the status is not sucessful, raise requests.HTTPError
    response.raise_for_status()


    # The following example gets the setup parameters and prints them to the log
    max_log_batch = helper.get_global_setting("max_log_batch")
    helper.log_info("max_log_batch={}".format(max_log_batch))

    # The following example gets the alert action parameters and prints them to the log
    user_id = helper.get_param("user_id")
    helper.log_info("user_id={}".format(user_id))

    okta_org = helper.get_param("okta_org")
    helper.log_info("okta_org={}".format(okta_org))

    change_state_to = helper.get_param("change_state_to")
    helper.log_info("change_state_to={}".format(change_state_to))


    # The following example adds two sample events ("hello", "world")
    # and writes them to Splunk
    # NOTE: Call helper.writeevents() only once after all events
    # have been added
    helper.addevent("hello", sourcetype="sample_sourcetype")
    helper.addevent("world", sourcetype="sample_sourcetype")
    helper.writeevents(index="summary", host="localhost", source="localhost")

    # The following example gets the events that trigger the alert
    events = helper.get_events()
    for event in events:
        helper.log_info("event={}".format(event))

    # helper.settings is a dict that includes environment configuration
    # Example usage: helper.settings["server_uri"]
    helper.log_info("server_uri={}".format(helper.settings["server_uri"]))
    [sample_code_macro:end]
    """
    
    #input should be a URL (matches the username from our accounts saved
    okta_org = helper.get_param("okta_org")
    user_id = helper.get_param("user_id")
    change_state_to = helper.get_param("change_state_to")
    sourcetype="Okta" + change_state_to + "User"
    index="summary"
    source="Okta:IM2"
    
    #fetch the account using the URL
    global_account = helper.get_user_credential(okta_org)
    
    url = "https://" + okta_org + "/api/v1/users/" + user_id
    helper.log_debug("_okta_client Invoked with a url of: " + url)
    userAgent = "Splunk-Response/1.0"
    method = "Get"
    params = {}
    okta_token = global_account['password']
    
    headers = { 'Authorization': 'SSWS ' + okta_token, 
                'User-Agent': userAgent, 
                'Content-Type': 'application/json', 
                'accept': 'application/json' }
        
    response = helper.send_http_request \
               (
                   url, method, parameters=params, 
                   payload=None, headers=headers,
                   cookies=None, verify=True, cert=None,
                   timeout=90
                )
    r_headers = response.headers
    requestid = r_headers.pop('X-Okta-Request-Id','None')
    helper.log_debug("_okta_client returned response to requestid : " + requestid)
    
    try:
        results = response.json()
    except:
        results = response.text
        helper.log_error("_okta_client returned: " + result)
        
    if response.status_code > 299:
        helper.log_error("_okta_client returned an error: " + results['errorCode'] + " : " + results['errorSummary'] + " : requestid : " + requestid)
        event = change_state_to + " user for user_id=" + user_id + ", outcome=error"
        helper.writeevents(index=index, host="localhost", source=source)
    
    response.raise_for_status()
    
    helper.log_debug("_okta_client found: " + results['id'] + " in state " + results['status'] )
    
    if not change_state_to in results['_links']:
        helper.log_error("User is in an invalidState, cannot change state to: " + change_state_to )
        event = change_state_to + " user for user_id=" + user_id + ", outcome=skipped"
        helper.addevent(event, sourcetype=sourcetype)        
    else:
        url = results['_links'][change_state_to]['href']
        method = results['_links'][change_state_to]['method']
        helper.log_debug("moving forward to " + change_state_to + " user at this URL: " + url )        

        response = helper.send_http_request \
               (
                   url, method, parameters=params, 
                   payload=None, headers=headers,
                   cookies=None, verify=True, cert=None,
                   timeout=90
                )
        r_headers = response.headers
        requestid = r_headers.pop('X-Okta-Request-Id','None')
        helper.log_debug("_okta_client returned response to requestid : " + requestid)
        
        try:
            results = response.json()
        except:
            results = response.text
            helper.log_error("_okta_client returned: " + result)
            
        if response.status_code > 299:
            helper.log_error("_okta_client returned an error: " + results['errorCode'] + " : " + results['errorSummary'] + " : requestid : " + requestid)
            event = change_state_to + " user for user_id=" + user_id + ", outcome=error"
            helper.writeevents(index=index, host="localhost", source=source)
        
        response.raise_for_status()
    
        event = change_state_to + " user for user_id=" + user_id + ", outcome=success"
        helper.addevent(event, sourcetype=sourcetype)
    
    helper.writeevents(index=index, host="localhost", source=source)
    return 0