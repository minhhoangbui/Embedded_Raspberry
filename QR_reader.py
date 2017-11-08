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

camera = None
raw = None
wireless = None
token_dict = {
    'dealer': None,
    'user': dict()
}


def set_up_gpio(BUZZ, ECHO, TRIG):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZ, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)
    GPIO.setup(TRIG, GPIO.OUT)


def set_up_camera():
    global camera, raw
    camera = PiCamera()
    camera.resolution = (640, 480)
    camera.framerate = 32
    raw = PiRGBArray(camera, size=(640, 480))
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


def buzz_done(BUZZ):
    GPIO.output(BUZZ, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(BUZZ, GPIO.HIGH)


def buzz_error(BUZZ):
    GPIO.output(BUZZ, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(BUZZ, GPIO.HIGH)
    time.sleep(0.1)
    GPIO.output(BUZZ, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(BUZZ, GPIO.HIGH)


def scan_qr():
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


def parsing_token(decoded):
    if decoded.find('setup') != -1:
        tmp = decoded.split('/')
        return (tmp[-3], tmp[-2], tmp[-1])
    elif decoded.find('shutdown') != -1:
        call(decoded, shell=True)
    else:
        return decoded[decoded.find('n=') + 2:]


if __name__ == "__main__":
    BUZZ = 2
    TRIG = 4
    ECHO = 18
    lambda_url = 'https://zwukd6rjqk.execute-api.us-east-1.amazonaws.com/prod/email_open_checker?token='
    set_up_gpio(BUZZ, ECHO, TRIG)
    buzz_done(BUZZ)
    set_up_camera()
    while True:
        dist = get_distance(TRIG, ECHO)
        time.sleep(0.2)
        if dist < 15. and dist > 6.:
            decoded = scan_qr()
        else:
            continue
        if decoded is None:
            continue
        try:
            result = parsing_token(decoded)
            is_dealer_token = isinstance(result, tuple)
            if is_dealer_token:
                ssid = result[0]
                psk = result[1]
                token = result[2]
                # set_up_wifi()
                if token_dict['dealer'] is None:
                    token_dict['dealer'] = token
                continue
            if not token_dict['user'].has_key(result) and not token_dict['dealer'] is None:
                token_dict['user'][result] = None
                try:
                    print lambda_url + token_dict['dealer'] + '&' + result
                    buzz_done(BUZZ)
                    # rsp = requests.get(lambda_url + token_dict['dealer'] + '&' + result, timeout=2)
                    # if rsp.status_code == 200:
                    # buzz_done(BUZZ)
                except requests.exceptions.ConnectionError:
                    time.sleep(1)
        except Exception as e:
            print(e)
            traceback.print_exc(file=sys.stdout)
            pass

