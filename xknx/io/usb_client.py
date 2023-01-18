from __future__ import annotations

import logging
from queue import Queue
from typing import TYPE_CHECKING

from xknx.cemi import CEMIFrame
from xknx.exceptions.exception import USBDeviceNotFoundError
from xknx.io.connection import ConnectionConfigUSB
from xknx.usb import (
    USBKNXInterfaceData,
    USBReceiveThread,
    USBSendThread,
    get_all_known_knx_usb_devices,
)
from xknx.usb.util import USBDevice

if TYPE_CHECKING:
    from xknx.xknx import XKNX

logger = logging.getLogger("xknx.log")


class USBClient:
    """Initializes the USB interface and start the send and receive threads"""

    def __init__(self, xknx: XKNX, connection_config: ConnectionConfigUSB) -> None:
        self.xknx = xknx
        self.connection_config = connection_config
        self.id_vendor = self.connection_config.idVendor
        self.id_product = self.connection_config.idProduct
        self.usb_device: USBDevice | None = None
        self._usb_send_thread: USBSendThread | None = None
        self._usb_receive_thread: USBReceiveThread | None = None
        self._send_queue: Queue[CEMIFrame] = Queue()

    @property
    def interface_data(self):
        """ """
        return USBKNXInterfaceData(self.id_vendor, self.id_product)

    def start(self) -> None:
        """ """
        all_knx_usb_devices = get_all_known_knx_usb_devices(self.id_vendor, self.id_product)
        if len(all_knx_usb_devices) > 0:
            self.usb_device = all_knx_usb_devices[0]

        if not self.usb_device:
            message = f"Could not find a/any KNX device (idVendor: {self.id_vendor}, idProduct: {self.id_product})"
            logger.error(message)
            raise USBDeviceNotFoundError(message)

        self.usb_device.use()
        self._usb_send_thread = USBSendThread(
            self.xknx, self.usb_device, self._send_queue
        )
        self._usb_receive_thread = USBReceiveThread(
            self.xknx, self.usb_device, self.xknx.telegrams
        )
        self._usb_send_thread.start()
        self._usb_receive_thread.start()

    def stop(self) -> None:
        """ """
        self._usb_send_thread.stop()
        self._usb_receive_thread.stop()
        self._usb_send_thread.join(timeout=5.0)
        self._usb_receive_thread.join(timeout=5.0)
        logger.debug(f"{self._usb_send_thread.name} stopped")
        logger.debug(f"{self._usb_receive_thread.name} stopped")
        if self.usb_device:
            self.usb_device.release()
        self.usb_device = None

    def connect(self) -> bool:
        """Claims the USB intercace"""
        self.usb_device.use()  # claims the interface and sets up the endpoints for read/write
        return True

    def disconnect(self) -> None:
        """Releases the USB intercace"""
        self.usb_device.release()

    def send_cemi(self, cemi: CEMIFrame) -> None:
        """
        Puts the CEMIFrame into the send queue, where the send thread will
        eventually get and send it
        """
        logger.debug(f"sending: {cemi}")
        self._send_queue.put(cemi)
