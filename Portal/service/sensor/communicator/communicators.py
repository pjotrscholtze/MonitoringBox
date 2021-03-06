import os
import threading
from typing import Callable
import io

import datetime
import service.serial.manager
import service.sensor.camera
from service.sensor_manager import Sensor, SensorType


def _get_index(str_in: str, find: str):
    out = -1
    try:
        out = str_in.index(find)
    except:
        pass
    return out


def _recursive_unwrapper(data):
    out = {}
    merging = {}
    for element in data:
        element = element  # type: str
        array_start = _get_index(element, "[")
        object_start = _get_index(element, ".")
        if array_start != -1 or object_start != -1:
            if array_start != -1 and object_start != -1:
                pass
            elif array_start != -1:
                first_part = element[0:array_start]
                second_part = element[array_start + 1:]
                second_part = second_part[:second_part.index("]")]
                if first_part not in merging:
                    merging[first_part] = []
                merging[first_part].insert(int(second_part), data[element])
            elif object_start != -1:
                first_part = element[0:object_start]
                second_part = element[object_start + 1:]
                if first_part not in merging:
                    merging[first_part] = []
                merging[first_part][second_part] = data[element]
        else:
            out[element] = data[element]

    for element in merging:
        out[element] = merging[element]
    return out


def _generic_callback_handler(data,
                              connection: service.serial.manager.SerialConnection,
                              callback_options):
    data["data"] = _recursive_unwrapper(data["data"])
    callback_options["callback"](data, connection, callback_options["options"])


def _sync_callback(data, connection: service.serial.manager.SerialConnection,
                   callback_options):
    callback_options["results"] = data
    # Will make the object available again.
    callback_options["lock"].release()
    callback_options["done"] = True


class AbstractCommunicator:
    def get_help(self, sensor: Sensor, callback: Callable, callback_options):
        command = "help"
        options = ""
        callback_options_wrapper = {"options": callback_options,
                                    "callback": callback}
        sensor.connection.send_command(command, options,
                                       _generic_callback_handler,
                                       callback_options_wrapper)

    def get_sensor_values(self, sensor: Sensor, callback: Callable, options):
        raise NotImplemented()

    def synchronous_call(self, function: Callable, sensor: Sensor, options):
        _lock = threading.Lock()  # type: threading.Lock

        callback_options = {
            "options": options,
            "lock": _lock,
            "results": None,
            "done": False
        }
        # Will lock the request.
        _lock.acquire()
        function(sensor, _sync_callback, callback_options)

        # Will lock the request. But that can only be done, after the previous
        # one is unlocked, which happens when the response comes back :)
        _lock.acquire()

        # Lets be nice and just release it.
        _lock.relase()
        return callback_options["results"]


class AbstractArduinoCommunicator(AbstractCommunicator):
    def get_sensor_values(self, sensor: Sensor, callback: Callable,
                          callback_options):
        command = self.get_command()
        options = self.get_options()
        callback_options_wrapper = {"options": callback_options,
                                    "callback": callback}
        sensor.connection.send_command(command, options,
                                       _generic_callback_handler,
                                       callback_options_wrapper)

    def get_command(self) -> str:
        return ""

    def get_options(self) -> str:
        return ""


class ExampleCommunicator(AbstractArduinoCommunicator):
    def get_command(self) -> str:
        return "getCurrentCount"


class HumidityTemperatureSensorCommunicator(AbstractArduinoCommunicator):
    def get_command(self) -> str:
        return "getCurrentCount"


class CO2SensorCommunicator(AbstractArduinoCommunicator):
    def get_command(self) -> str:
        return "getValue"


class HeartRateSensorCommunicator(AbstractArduinoCommunicator):
    def get_command(self) -> str:
        return "getCurrentCount"


class PiCamCommunicator(AbstractCommunicator):
    def get_sensor_values(self, sensor: Sensor, callback: Callable,
                          callback_options):
        recording = callback_options["recording"]  # type: Recording
        if not os.path.exists(recording.path):
            os.mkdir(recording.path)
        photo_folder = os.path.join(recording.path, "PI_CAMERA")
        if not os.path.exists(photo_folder):
            os.mkdir(photo_folder)
        now = datetime.datetime.now()
        photo_path = os.path.join(photo_folder,
                                  now.strftime("%y.%m.%d@%H.%M.%S.%f.jpg"))
        service.sensor.camera.camera.capture(photo_path)

        callback({
            "location": photo_path,
            "date": now.strftime("%y-%m-%d"),
            "time": now.strftime("%H-%M-%S")
        }, None, callback_options)


class GSRSensorCommunicator(AbstractArduinoCommunicator):
    def get_command(self) -> str:
        return "getCurrentCount"


def get_communicator_instance(sensor: Sensor) -> AbstractArduinoCommunicator:
    if sensor.sensor_type == SensorType.EXAMPLE_SENSOR:
        return ExampleCommunicator()
    elif sensor.sensor_type == SensorType.PI_CAMERA:
        return PiCamCommunicator()
    elif sensor.sensor_type == SensorType.HUMIDITY_TEMPERATURE_SENSOR:
        return HumidityTemperatureSensorCommunicator()
    elif sensor.sensor_type == SensorType.CO2_SENSOR:
        return CO2SensorCommunicator()
    elif sensor.sensor_type == SensorType.HEART_RATE_SENSOR:
        return HeartRateSensorCommunicator()
    elif sensor.sensor_type == SensorType.GALVANIC_SKIN_RESPONSE_SENSOR:
        return GSRSensorCommunicator()
    raise Exception("Unkown sensor")
