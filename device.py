import dataclasses

@dataclasses.dataclass
class AppleDevice:
    """Represents a single Apple device with its latest firmware information."""
    hardware_code: str
    build_version: str
    firmware_sha1: str
    firmware_url: str
    product_version: str

    def __str__(self):
        """Returns a user-friendly string representation of the device."""
        return (
            f"Device: {self.hardware_code}\n"
            f"  Product Version: {self.product_version}\n"
            f"  Build Version:   {self.build_version}\n"
            f"  Firmware SHA1:   {self.firmware_sha1}\n"
            f"  Firmware URL:    {self.firmware_url}"
        )