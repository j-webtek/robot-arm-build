"""Inert, one-use adapter around reviewed esptool 4.6 and an explicit USB port.

No dependency import/search or port discovery occurs here. The authorized caller
supplies pinned modules. First identity() opens/resets the controller; construction
does not. The caller must review reset/startup behavior and obtain authorization
for the physical power/support state. This adapter neither removes motor power
nor sends servo commands; a controller reset can still have physical effects.
"""
import io
from types import SimpleNamespace

from rocell.application.startup_provisioning_execution import (
    FLASH_SIZE, FS_START, IMAGE_SIZE, MAC,
)


class StartupProvisioningDevice:
    def __init__(self, *, esptool, cmds, loader, serial, port='COM7'):
        if esptool.__version__ != '4.6' or port != 'COM7':
            raise ValueError('Unreviewed provisioning dependency or port')
        self.api, self.cmds, self.loader, self.serial = esptool, cmds, loader, serial
        self.port_name = port
        self.port = self.stub = None
        self.open_attempted = self.write_attempted = self.closed = False
        self.reads = 0
        self.startup_attempted = False

    def identity(self):
        if self.open_attempted or self.closed:
            raise ValueError('USB connection attempt already consumed')
        self.open_attempted = True
        self.port = self.serial.Serial(port=None, baudrate=115200, timeout=3, write_timeout=10)
        self.port.dtr = False
        self.port.rts = False
        self.port.port = self.port_name
        try:
            self.port.open()
            rom = self.api.ESP32ROM(self.port, baud=115200)
            rom.connect('default_reset', attempts=1)
            identity = dict(mac=':'.join(f'{v:02x}' for v in rom.read_mac()),
                secure_boot=bool(rom.get_secure_boot_enabled()),
                flash_encryption=bool(rom.get_flash_encryption_enabled()),
                secure_download_mode=bool(rom.secure_download_mode))
            if (identity['mac'] != MAC or rom.stub_is_disabled or
                    any(identity[k] for k in ('secure_boot', 'flash_encryption', 'secure_download_mode'))):
                raise ValueError('USB controller incompatible')
            self.stub = rom.run_stub()
            identity['flash_id'] = self.stub.flash_id()
            if identity['flash_id'] != 0x164020:
                raise ValueError('Unexpected flash identity')
            return identity
        except BaseException:
            self.close()
            raise

    def read_flash(self, offset, length):
        if self.closed or self.stub is None or offset != 0 or length != FLASH_SIZE or self.reads >= 2:
            raise ValueError('Unreviewed flash read')
        if self.reads == 1 and not self.write_attempted:
            raise ValueError('Second read only follows the one write')
        self.reads += 1
        try:
            return self.stub.read_flash(offset, length)
        except BaseException:
            self.close()
            raise

    def write_flash_once(self, offset, image):
        if (self.closed or self.stub is None or self.write_attempted or self.reads != 1 or
                offset != FS_START or type(image) is not bytes or len(image) != IMAGE_SIZE):
            raise ValueError('Unreviewed or repeated filesystem write')
        self.write_attempted = True
        # This adapter runs in a dedicated process; do not restore a retry default
        # that could permit a later accidental write to retry in that process.
        self.loader.WRITE_BLOCK_ATTEMPTS = 1
        stream = io.BytesIO(image)
        stream.name = 'reviewed-startup-filesystem.bin'
        args = SimpleNamespace(addr_filename=[(offset, stream)], compress=True,
            no_compress=False, no_stub=False, force=False, encrypt=False,
            encrypt_files=None, erase_all=False, verify=False,
            ignore_flash_encryption_efuse_setting=False,
            flash_size='keep', flash_mode='keep', flash_freq='keep')
        try:
            with stream:
                self.cmds.write_flash(self.stub, args)
            return True
        except BaseException:
            self.close()
            raise

    def close(self):
        # Never reset/startup on close, including failure paths.
        self.closed = True
        if self.port is not None:
            self.port.close()

    def startup_once(self):
        """Caller must have verified readback AND durable export before calling."""
        if (self.closed or self.stub is None or not self.write_attempted or
                self.reads != 2 or self.startup_attempted):
            raise ValueError('Startup not eligible or already attempted')
        self.startup_attempted = True
        try:
            self.stub.hard_reset()
        finally:
            self.close()
