import serial
import time

PORT = "/dev/sensors/ftdi_12345"
PSPEED = 9600
CACHE_TIME = 1


cache = {}


def get_values(port=PORT, pspeed=PSPEED):
    lines = {}
    line = ""
    cache_key = port
    ts = time.time()

    if cache.get(cache_key, None) and \
            cache[cache_key]["ts"] + CACHE_TIME > ts:
        return cache[cache_key]["value"]

    try:
        ser = serial.Serial(PORT, PSPEED)
    except:
        return lines

    while line != ">":
        line = ser.readline().decode("latin-1").strip()

    line = ser.readline().decode("latin-1").strip()

    while line != "<":
        key, value = line.split(":")
        try:
            lines[key.strip()] = float(value.strip())
        except:
            pass
        line = ser.readline().decode("latin-1").strip()

    cache[cache_key] = {
        "ts": ts,
        "value": lines,
    }

    return lines


def get_value(port, pspeed, sensor):
    return get_values(port, pspeed).get(sensor, None)


if __name__ == "__main__":
    while True:
        try:
            ser = serial.Serial(PORT, PSPEED)
        except:
            print("Device not available...")
            time.sleep(10)
            continue

        c = ""

        while c != ">":
            c = ser.readline().decode("latin-1").strip()

        c = ser.readline().decode("latin-1").strip()

        while c != "<":
            print(c)
            c = ser.readline().decode("latin-1").strip()

        print("---")

        time.sleep(1)
