import RPi.GPIO as GPIO
import time
from picamera.array import PiRGBArray
from picamera import PiCamera
import zbar
import cv2
from PIL import Image
import requests
from subprocess import call
import sys, traceback
import os
import subprocess
import urllib
import socket

camera = None
raw = None
wireless = None
token_dict = {
    'dealer': None,
    'user': set()
}


def set_up_gpio(BUZZ, ECHO, TRIG, GREEN, RED):
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(BUZZ, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)
    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(GREEN, GPIO.OUT)
    GPIO.setup(RED, GPIO.OUT)


def set_up_camera():
    global camera, raw
    camera = PiCamera()
    camera.resolution = (720, 720)
    camera.framerate = 32
    raw = PiRGBArray(camera, size=(720, 720))
    time.sleep(0.1)


def get_distance(TRIG, ECHO):
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)
    start = 0
    end = 0
    while GPIO.input(ECHO) == False:
        start = time.time()
    while GPIO.input(ECHO) == True:
        end = time.time()
    return (end - start) / 0.000058


def buzz_1(BUZZ):
    GPIO.output(BUZZ, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(BUZZ, GPIO.HIGH)


def led(color):
    GPIO.output(color, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(color, GPIO.LOW)


def buzz_2(BUZZ):
    GPIO.output(BUZZ, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(BUZZ, GPIO.HIGH)
    time.sleep(0.1)
    GPIO.output(BUZZ, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(BUZZ, GPIO.HIGH)


def buzz_long(BUZZ):
    GPIO.output(BUZZ, GPIO.LOW)
    time.sleep(1)
    GPIO.output(BUZZ, GPIO.HIGH)


def scan_qr(BUZZ, RED):
    tmp = 0
    for frame in camera.capture_continuous(raw, format='bgr', use_video_port=True):
        img = frame.array
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        image = Image.fromarray(gray)
        width, height = image.size
        z_img = zbar.Image(width, height, 'Y800', image.tobytes())
        scanner = zbar.ImageScanner()
        res = scanner.scan(z_img)
        print res
        if res > 0:
            for decoded in z_img:
                raw.truncate(0)
                return decoded.data
            break
        elif res == -1:
            led_error(RED)
            buzz_error(BUZZ)
            raw.truncate(0)
            continue
        else:
            if tmp == 0:
                start = time.time()
                tmp += 1
            else:
                if time.time() - start > 5:
                    raw.truncate(0)
                    break
            raw.truncate(0)


def parsing_token(decoded, RED, BUZZ):
    if decoded.find('setup') != -1:
        tmp = decoded.split('/')
        return (tmp[-3], tmp[-2], tmp[-1])
    elif decoded.find('shutdown') != -1:
        led(RED)
        buzz_2(BUZZ)
        call(decoded, shell=True)
    else:
        return decoded[decoded.find('n=') + 2:]


def connect_wifi(ssid, psk):
    disconnect = "sudo wpa_cli -i wlan0 disconnect"
    remove = "sudo wpa_cli -i wlan0 remove_network 0"
    add = "sudo wpa_cli -i wlan0 add_network"
    set_ssid = "sudo wpa_cli -i wlan0 set_network 0 ssid '\"%s\"'" % ssid
    set_psk = "sudo wpa_cli -i wlan0 set_network 0 psk '\"%s\"'" % psk
    enable = "sudo wpa_cli -i wlan0 enable_network 0"
    reconnect = "sudo wpa_cli -i wlan0 reconnect 0"
    dhcp_0 = "sudo dhclient -r"
    dhcp_1 = "sudo dhclient wlan0"
    os.system(disconnect)
    os.system(remove)
    os.system(add)
    a = subprocess.check_output(set_ssid, shell=True).strip()
    b = subprocess.check_output(set_psk, shell=True).strip()
    c = subprocess.check_output(enable, shell=True).strip()
    d = subprocess.check_output(reconnect, shell=True).strip()
    p = subprocess.Popen(dhcp_0, shell=True)
    p.wait()
    p = subprocess.Popen(dhcp_1, shell=True)
    p.wait()
    os.system("sudo pkill -f dhclient")
    if a == 'OK' and b == 'OK' and c == 'OK' and d == 'OK':
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        print s.getsockname()[0]
        return True
    return False


def insert_dealer(token):
    file = open('dealer_list.txt', 'w')
    file.write("\n%s" % token)
    file.close()


if __name__ == "__main__":
    BUZZ = 2
    TRIG = 4
    ECHO = 18
    GREEN = 20
    RED = 21
    # Try to get the last dealer in the list
    try:
        token_dict['dealer'] = subprocess.check_output(['tail', '-1', 'dealer_list.txt'])
    except Exception as e:
        print e
        pass
    # Set up the system
    try:
        set_up_gpio(BUZZ, ECHO, TRIG, GREEN, RED)
        led(GREEN)
        buzz_2(BUZZ)
        set_up_camera()
    except Exception as e:
        print(e)
        traceback.print_exc(file=sys.stdout)
        os.system("sudo reboot")
    # Check Internet Connection

    while True:
        try:
            subprocess.check_output("ping -W 1 -c 2 8.8.8.8", shell=True)
            GPIO.output(RED, GPIO.LOW)
        except Exception:
            GPIO.output(RED, GPIO.HIGH)

        dist = get_distance(TRIG, ECHO)
        time.sleep(0.05)
        if dist < 15. and dist > 5.:
            decoded = scan_qr(BUZZ, RED)
        else:
            continue
        if decoded is None:
            continue
        else:
            led(GREEN)
        try:
            result = parsing_token(decoded, RED, BUZZ)
            print result
            is_dealer_token = isinstance(result, tuple)
            if is_dealer_token:
                ssid = result[0]
                psk = result[1]
                token_dict['dealer'] = result[2]
                insert_dealer(result[2])
                try:
                    if not connect_wifi(ssid, psk):
                        raise RuntimeError
                    else:
                        led(GREEN)
                        buzz_2(BUZZ)
                except RuntimeError as e:
                    led(RED)
                    buzz_long(BUZZ)
                    print "Cannot connect Wifi"
                    continue
            elif not result in token_dict['user'] and not token_dict['dealer'] is None:
                print "user part"
                print result
                try:
                    rsp = requests.get(
                        'https://frxry2teyc.execute-api.us-east-1.amazonaws.com/prod/qrscanner?token=' + result + '&access_token=' +
                        token_dict['dealer'], timeout=2)
                    print rsp.status_code
                    rs = rsp.json()
                    print (rs)
                    if rsp.status_code == 200 and rs['code'] == 'success':
                        token_dict['user'].add(result)
                        print 'Sent ' + result
                        led(GREEN)
                        buzz_1(BUZZ)
                    else:
                        led(RED)
                        buzz_long(BUZZ)
                except requests.exceptions.ConnectionError:
                    print 'Connection error'
                    time.sleep(1)
        except Exception as e:
            print(e)
            traceback.print_exc(file=sys.stdout)
            pass


