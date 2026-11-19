# Utility: print this ESP32's Wi-Fi MAC address.
# Run once on each board and copy the result into the ESP-NOW peer lists in
# control_unit.py and tagger_*.py.

import network

def get_mac(interface_type=network.STA_IF):
    """
    Returns the formatted MAC address of the ESP32.

    :param interface_type: The type of network interface. Default is Wi-Fi Station Interface (network.STA_IF).
    :return: A string representing the formatted MAC address.
    """
    # Initialize the network interface
    wlan = network.WLAN(interface_type)

    # Activate the interface
    wlan.active(True)

    # Get the MAC address
    mac_address = wlan.config('mac')

    # Format the MAC address in a more readable form
    formatted_mac = ':'.join(['{:02x}'.format(b) for b in mac_address])

    return formatted_mac

# Example usage
print("Wi-Fi MAC address:", get_mac())
