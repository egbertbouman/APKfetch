import os
import sys
import json
import gzip
import urllib
import binascii
import argparse
import requests
import StringIO

GOOGLE_LOGIN_URL = 'https://android.clients.google.com/auth'
GOOGLE_DETAILS_URL = 'https://play.google.com/store/apps/details?id='
GOOGLE_PURCHASE_URL = 'https://android.clients.google.com/fdfe/purchase'


def get_var_int(buffer, position):
    b = ord(buffer[position])
    i = b & 0x7F
    shift = 7
    while (b & 0x80) != 0:
        position += 1
        b = ord(buffer[position])
        i |= (b & 0x7F) << shift
        shift += 7
    return i


class APKfetch(object):

    def __init__(self):
        self.session = requests.Session()
        self.user = self.passwd = self.device_id = None

    def login(self, user, passwd, androidid):
        self.user = user
        self.passwd = passwd
        self.androidid = androidid

        self.session.headers.update({'User-Agent': 'Android-Finsky/5.7.10 (api=3,versionCode=80371000,sdk=19,device=falcon_umts,hardware=qcom,product=falcon_reteu,platformVersionRelease=4.4.4,model=XT1032,buildId=KXB21.14-L1.40,isWideScreen=0)',
                                     'Content-Type': 'application/x-www-form-urlencoded',
                                     'device': self.androidid})

        encoded_json = urllib.urlencode({'accountType': 'HOSTED_OR_GOOGLE',
                                         'system_partition': '1',
                                         'has_permission': '1',
                                         'add_account': '1',
                                         'service': 'androidmarket',
                                         'source': 'android',
                                         'androidId': self.androidid,
                                         'get_accountid': '1',
                                         'Email': self.user,
                                         'app': 'com.android.vending',
                                         'Passwd': self.passwd})
        response = self.session.post(GOOGLE_LOGIN_URL, data=encoded_json, allow_redirects=True)

        for line in response.text.splitlines():
            if line.startswith('Auth'):
                self.auth = line

        return self.auth is not None

    def version(self, package_name):
        # TODO: use /fdfe/details
        response = self.session.get(GOOGLE_DETAILS_URL + package_name, allow_redirects=True)
        search_str = r'</button> </li><li role="menuitem" tabindex="-1"> <button class="dropdown-child" data-dropdown-value="'
        i1 = response.content.find(search_str)
        i2 = response.content.find(search_str, i1 + 1) + len(search_str)
        i3 = response.content.find('"', i2)
        return response.content[i2:i3]

    def fetch(self, package_name):
        headers = {'X-DFE-Device-Id': self.androidid,
                   'X-DFE-Client-Id': 'am-android-google',
                   'Accept-Encoding': '',
                   'Host': 'android.clients.google.com',
                   'Authorization': 'GoogleLogin ' + self.auth}

        encoded_json = urllib.urlencode({'doc': package_name,
                                         'ot': '1',
                                         'vc': self.version(package_name),
                                         'tok': 'dummy-token'})
        response = self.session.post(GOOGLE_PURCHASE_URL, data=encoded_json, headers=headers, allow_redirects=True)

        # Extract URLs from response
        # TODO: use protobuf
        urls = []
        index = 0
        content = response.content
        while content.find('http', index) >= 0:
            index = content.find('http', index)
            length = get_var_int(content, index - 2)
            urls.append(content[index:index + length])
            index += 1

        # Extract MarketDA value
        index = content.find('MarketDA')
        length = get_var_int(content, index + 9)
        marketda = content[index + 10:index + length + 10]

        response = self.session.get(urls[1], headers={'User-Agent': 'AndroidDownloadManager/4.4.4 (Linux; U; Android 4.4.4; XT1032 Build/KXB21.14-L1.40)'},
                                    cookies={'MarketDA': marketda}, allow_redirects=True)

        buffer = StringIO.StringIO(response.content)
        gzip_file = gzip.GzipFile(mode="rb", fileobj=buffer)
        uncompressed = gzip_file.read()

        apk_fn = package_name + '.apk'
        if os.path.exists(apk_fn):
            os.remove(apk_fn)

        with open(apk_fn, 'wb') as fp:
            fp.write(uncompressed)

        return os.path.exists(apk_fn)


def main(argv):
    parser = argparse.ArgumentParser(add_help=False, description=('Fetch APK files from the Google Play store'))
    parser.add_argument('--help', '-h', action='help', default=argparse.SUPPRESS, help='Show this help message and exit')
    parser.add_argument('--user', '-u', help='Google username')
    parser.add_argument('--passwd', '-p', help='Google password')
    parser.add_argument('--androidid', '-a', help='AndroidID')
    parser.add_argument('--package', '-k', help='Package name of the app')

    try:
        args = parser.parse_args(sys.argv[1:])

        user = args.user
        passwd = args.passwd
        androidid = args.androidid
        package = args.package

        if not user or not passwd or not androidid or not package:
            parser.print_usage()
            raise ValueError('user, passwd, androidid, and package are required options')

        apk = APKfetch()
        apk.login(user, passwd, androidid)
        apk.fetch(package)

    except Exception, e:
        print 'Error:', str(e)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
