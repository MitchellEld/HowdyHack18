import requests
import os
import base64
from pathlib import Path
import html
import uuid

print_cred_file = os.path.dirname(os.path.abspath('custom_commands'))+'/custom_commands/aggieprint_creds'

print_file_path = Path(print_cred_file)
if not print_file_path.exists():
    open(print_cred_file, 'a').close()

login_headers = {
    'X-Authorization': 'PHAROS-USER <base64 encoded "netid:pass">', # PHAROS-USER base64encoded(netid:password)
    'Referer': 'https://aggieprint.tamu.edu/myprintcenter/',
    'Host': 'aggieprint.tamu.edu',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Accept': '*/*'
}

login_params = {
    'KeepMeLoggedIn': 'no',
    'includeprintjobs': 'no',
    'includedeviceactivity': 'yes',
    'includeprivileges': 'yes',
    'includecostcenters': 'yes',
    'excudeLocation': 'yes',
    'notRefreshBalance': 'no',
    '_request': uuid.uuid4(),
    '_': '1537066069771'
}

login_url = 'https://aggieprint.tamu.edu/PharosAPI/logon'

upload_params = {
    '_request': uuid.uuid4()
}

upload_headers = {
    'Referer': 'https://aggieprint.tamu.edu/myprintcenter/',
    'Host': 'aggieprint.tamu.edu',
    'Accept': '*/*',
    'Cookie': ''
}
# 'https://aggieprint.tamu.edu/PharosAPI/users/asxktmuIqDH9LBCNzvm_cw2/printjobs'
upload_url = 'https://aggieprint.tamu.edu/PharosAPI'

cookie_names = ['PharosAPI.SignIn.Token', 'PharosAPI.X-PHAROS-USER-TOKEN', 'PharosAPI.X-PHAROS-USER-URI']

ext2type = {
    'txt': 'text/plain',
    'pdf': 'application/pdf',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'rtf': 'text/rtf',
    'csv': 'text/csv'
}

def get_content_type(filename):
    name_parts = filename.split('.')
    extension = name_parts[len(name_parts)-1]
    if extension in ext2type:
        return ext2type[extension]
    return extension

def set_login(username, password):
    username = str(base64.b64encode(bytes(username, 'utf-8')),'utf-8')
    password = str(base64.b64encode(bytes(password, 'utf-8')),'utf-8')
    with open(print_cred_file, 'w') as cred_file:
        cred_file.write(username+'\n')
        cred_file.write(password)

# parse the parameters/flags and return dictionary of allowed flags
def parse_flags(flags):
    parsed_flags = {
        'u': '',
        'p': '',
        'filename': ''
    }
    # set login parsing
    if flags[0] == 'set-login':
        if len(flags) != 3:
            return "Invalid number of parameters to login"
        usr = flags[1]
        pwd = flags[2]
        set_login(usr, pwd)
        return 'Login credentials have been set'
    else:
        if len(flags) == 1:
            with open(print_cred_file, 'r') as cred_file:
                creds = cred_file.read().split('\n')
                if len(creds) == 2:
                    parsed_flags['u'] = str(base64.b64decode(bytes(creds[0], 'utf-8')), 'utf-8')
                    parsed_flags['p'] = html.unescape(str(base64.b64decode(bytes(creds[1],'utf-8')), 'utf-8'))
                else:
                    return 'You need to set your login credentials'
            # print(flags)
            parsed_flags['filename'] = flags[0]
        else:
            return 'Invalid number of parameters to print'
    
    return parsed_flags
    
# Aggieprint custom command
def aggieprint(flags):
    # parse flags for login
    flag_values = parse_flags(flags)
    if type(flag_values) == str:
        return flag_values

    userpass = str(base64.b64encode(bytes('{}:{}'.format(flag_values['u'], flag_values['p']), 'utf-8')), 'utf-8')

    # Set login header
    login_headers['X-Authorization'] = 'PHAROS-USER {}'.format(userpass)

    # Login for auth tokens
    res = requests.get(login_url, params=login_params, headers=login_headers)
    if res.status_code < 200 and res.status_code >= 300:
        return 'Authentication did not work'

    user_uri = ''
    # Get the cookies from the login response and concatenate the cookies to a single string for the print request header
    complete_cookie_string = ''
    for cookie_name in cookie_names:
        if cookie_name in res.cookies:
            if cookie_name == 'PharosAPI.X-PHAROS-USER-URI':
                user_uri = res.cookies[cookie_name]
            complete_cookie_string += '{}={}; '.format(cookie_name,res.cookies[cookie_name])

    for i in range(len(cookie_names)):
        if cookie_names[i] in res.cookies:
            # print('COOKIE:',cookie_names[i], ': ', res.cookies[cookie_names[i]])
            if i != len(cookie_names)-1:
                complete_cookie_string += '{}={}; '.format(cookie_names[i],res.cookies[cookie_names[i]])
            else:
                complete_cookie_string += '{}={}'.format(cookie_names[i],res.cookies[cookie_names[i]])

    upload_headers['Cookie'] = complete_cookie_string

    # Metadata as part of the file upload
    upload_meta = '{"FinishingOptions":{"Mono":true,"Duplex":false,"PagesPerSide":"1","Copies":"1","DefaultPageSize":"Letter","PageRange":""},"PrinterName":""}'

    content_type = get_content_type(flag_values['filename'])
    if content_type not in ext2type.values():
        return 'No support for {} file type'.format(content_type)

    file = open(flag_values['filename'],'rb')
    upload_file = {'MetaData': upload_meta, 'content': (flag_values['filename'], file, content_type)} # Add dynamic content-type and filename

    # Request file upload
    up_res = requests.post('{}{}/printjobs'.format(upload_url,user_uri), headers=upload_headers, files=upload_file)

    if up_res.status_code >= 200 and up_res.status_code < 300:
        return 'File should be uploaded'
    elif 'authenticated' in up_res.text.lower():
        return 'There seems to have been a problem with authentication'
    else:
        return 'There was some kind of problem uploading'

