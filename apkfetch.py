import os
import sys
import json
import gzip
import time
import argparse
import requests
import StringIO

import apkfetch_pb2

GOOGLE_LOGIN_URL = 'https://android.clients.google.com/auth'
GOOGLE_CHECKIN_URL = 'https://android.clients.google.com/checkin'
GOOGLE_DETAILS_URL = 'https://play.google.com/store/apps/details?id='
GOOGLE_PURCHASE_URL = 'https://android.clients.google.com/fdfe/purchase'

LOGIN_USER_AGENT = 'GoogleLoginService/1.3 (gio KOT49H)'
MARKET_USER_AGENT = 'Android-Finsky/5.7.10 (api=3,versionCode=80371000,sdk=19,device=falcon_umts,hardware=qcom,product=falcon_reteu,platformVersionRelease=4.4.4,model=XT1032,buildId=KXB21.14-L1.40,isWideScreen=0)'
CHECKIN_USER_AGENT = 'Android-Checkin/2.0 (gio KOT49H)'
DOWNLOAD_USER_AGENT = 'AndroidDownloadManager/4.4.4 (Linux; U; Android 4.4.4; XT1032 Build/KXB21.14-L1.40)'


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


def num_to_hex(num):
    hex_str = format(num, 'x')
    length = len(hex_str)
    return hex_str.zfill(length + length % 2)


class APKfetch(object):

    def __init__(self):
        self.session = requests.Session()
        self.user = self.passwd = self.androidid = self.token = self.auth = None
        
    def request_service(self, service, app, user_agent=LOGIN_USER_AGENT):
        self.session.headers.update({'User-Agent': user_agent,
                                     'Content-Type': 'application/x-www-form-urlencoded'})
        
        if self.androidid:
            self.session.headers.update({'device': self.androidid})

        data = {'accountType': 'HOSTED_OR_GOOGLE',
                'has_permission': '1',
                'add_account': '1',
                'get_accountid': '1',
                'service': service,
                'app': app,
                'source': 'android',
                'Email': self.user}
        
        if self.androidid:
            data['androidId'] = self.androidid
            
        if self.token:
            data['EncryptedPasswd'] = self.token
        else:
            data['Passwd'] = self.passwd

        response = self.session.post(GOOGLE_LOGIN_URL, data=data, allow_redirects=True)
        
        token = None
        auth = None
        for line in response.text.splitlines():
            if line.startswith('Token'):
                token = line[6:]
            if line.startswith('Auth'):
                auth = line
        return token, auth
        
    def checkin(self):
        headers = {'User-Agent': CHECKIN_USER_AGENT,
                   'Content-Type': 'application/x-protobuf'}

        cr = apkfetch_pb2.AndroidCheckinRequest()
        cr.id = 0
        cr.checkin.build.timestamp = int(time.time())
        cr.checkin.build.sdkVersion = 16
        cr.marketCheckin = self.user
        cr.accountCookie.append(self.auth[5:])
        cr.deviceConfiguration.touchScreen = 3
        cr.deviceConfiguration.keyboard = 1
        cr.deviceConfiguration.navigation = 1
        cr.deviceConfiguration.screenLayout = 2
        cr.deviceConfiguration.hasHardKeyboard = False
        cr.deviceConfiguration.hasFiveWayNavigation = False
        cr.deviceConfiguration.screenDensity = 320
        cr.deviceConfiguration.glEsVersion = 131072
        cr.deviceConfiguration.systemSharedLibrary.extend(["android.test.runner", "com.android.future.usb.accessory",
                                                           "com.android.location.provider", "com.android.nfc_extras", 
                                                           "com.google.android.maps", "com.google.android.media.effects",
                                                           "com.google.widevine.software.drm", "javax.obex"])
        cr.deviceConfiguration.systemAvailableFeature.extend(["android.hardware.bluetooth", "android.hardware.camera",
                                                              "android.hardware.camera.autofocus", "android.hardware.camera.flash",
                                                              "android.hardware.camera.front", "android.hardware.faketouch", 
                                                              "android.hardware.location", "android.hardware.location.gps",
                                                              "android.hardware.location.network", "android.hardware.microphone", 
                                                              "android.hardware.nfc", "android.hardware.screen.landscape",
                                                              "android.hardware.screen.portrait", "android.hardware.sensor.accelerometer",
                                                              "android.hardware.sensor.barometer", "android.hardware.sensor.compass",
                                                              "android.hardware.sensor.gyroscope", "android.hardware.sensor.light",
                                                              "android.hardware.sensor.proximity", "android.hardware.telephony",
                                                              "android.hardware.telephony.gsm", "android.hardware.touchscreen",
                                                              "android.hardware.touchscreen.multitouch", 
                                                              "android.hardware.touchscreen.multitouch.distinct",
                                                              "android.hardware.touchscreen.multitouch.jazzhand", 
                                                              "android.hardware.usb.accessory", "android.hardware.usb.host", 
                                                              "android.hardware.wifi", "android.hardware.wifi.direct",
                                                              "android.software.live_wallpaper", "android.software.sip",
                                                              "android.software.sip.voip", 
                                                              "com.google.android.feature.GOOGLE_BUILD", "com.nxp.mifare"])
        cr.deviceConfiguration.screenWidth = 720
        cr.deviceConfiguration.screenHeight = 1280
        cr.version = 3
        cr.fragment = 0

        response = self.session.post(GOOGLE_CHECKIN_URL, data=cr.SerializeToString(), headers=headers, allow_redirects=True)

        checkin_response = apkfetch_pb2.AndroidCheckinResponse()
        checkin_response.ParseFromString(response.content)
        token = num_to_hex(checkin_response.securityToken)
        androidid = num_to_hex(checkin_response.androidId)
        return token, androidid

    def login(self, user, passwd, androidid=None):
        self.user = user
        self.passwd = passwd
        self.androidid = androidid

        self.token, self.auth = self.request_service('ac2dm', 'com.google.android.gsf')

        if not androidid:
            _, self.androidid = self.checkin()
            print self.androidid
            
        _, self.auth = self.request_service('androidmarket', 'com.android.vending', MARKET_USER_AGENT)
            
        return self.auth is not None

    def version(self, package_name):
        # TODO: use /fdfe/details
        response = self.session.get(GOOGLE_DETAILS_URL + package_name, allow_redirects=True)
        search_str = r'</button> </li><li role="menuitem" tabindex="-1"> <button class="dropdown-child" data-dropdown-value="'
        i1 = response.content.find(search_str)
        i2 = response.content.find(search_str, i1 + 1) + len(search_str)
        i3 = response.content.find('"', i2)
        return response.content[i2:i3]

    def fetch(self, package_name, apk_fn=None):
        headers = {'X-DFE-Device-Id': self.androidid,
                   'X-DFE-Client-Id': 'am-android-google',
                   'Accept-Encoding': '',
                   'Host': 'android.clients.google.com',
                   'Authorization': 'GoogleLogin ' + self.auth}

        data = {'doc': package_name,
                'ot': '1',
                'vc': self.version(package_name),
                'tok': 'dummy-token'}
        response = self.session.post(GOOGLE_PURCHASE_URL, data=data, headers=headers, allow_redirects=True)

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

        response = self.session.get(urls[-1], headers={'User-Agent': DOWNLOAD_USER_AGENT}, 
                                    cookies={'MarketDA': marketda}, allow_redirects=True)

        if len(urls) > 1:
            buffer = StringIO.StringIO(response.content)
            gzip_file = gzip.GzipFile(mode="rb", fileobj=buffer)
            uncompressed = gzip_file.read()
        else:
            uncompressed = response.content

        apk_fn = apk_fn or (package_name + '.apk')
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

        if not user or not passwd or not package:
            parser.print_usage()
            raise ValueError('user, passwd, and package are required options')

        apk = APKfetch()
        apk.login(user, passwd, androidid)
        apk.fetch(package)

    except Exception, e:
        print 'Error:', str(e)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
