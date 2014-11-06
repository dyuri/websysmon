import serial
import time

PORT = "/dev/sensors/ftdi_12345"
PSPEED = 9600


def get_values(port=PORT, pspeed=PSPEED):
    lines = {}
    line = ""

    try:
        ser = serial.Serial(PORT, PSPEED)
    except:
        return lines

    while line != ">":
        line = ser.readline().decode("latin-1").strip()

    line = ser.readline().decode("latin-1").strip()

    while line != "<":
        key, value = line.split(":")
        lines[key.strip()] = float(value.strip())
        line = ser.readline().decode("latin-1").strip()

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