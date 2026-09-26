import can
import time

# --- Constants for OBD-II Communication ---
# Functional ID for requesting diagnostics from all ECUs (11-bit)
OBD_REQUEST_ID = 0x7DF 
# Standard ID for ECU 1 response (typically starts at 0x7E8)
ECU_RESPONSE_ID = 0x7E8 

# Service Mode 01 (Show Current Data)
SERVICE_MODE_01 = 0x01
# PID 01 (Monitor status since DTCs cleared)
PID_MIL_STATUS = 0x01
# Positive response code for Service Mode 01 (Mode + 40 = 0x41)
RESPONSE_MODE_01 = 0x41 

# Service Mode 03 (Request Emission-Related Diagnostic Trouble Codes)
SERVICE_MODE_03 = 0x03
# Positive response code for Service Mode 03 (Mode + 40 = 0x43)
RESPONSE_MODE_03 = 0x43 

def decode_dtc(dtc_bytes):
    """
    Decodes a 2-byte hexadecimal DTC value into the standard 5-character P/C/B/U format.
    
    The first two bits of the first byte determine the category (P/C/B/U).
    The remaining bits are converted to decimal digits.
    Example: 0x0100 -> P0100
    """
    if len(dtc_bytes) != 2:
        return f"Invalid DTC length ({len(dtc_bytes)})"

    b1 = dtc_bytes[0]
    b2 = dtc_bytes[1]

    # Map the first two bits (15 and 14) to the DTC category
    # Mask: 0b11 (3 in decimal)
    category_code = (b1 >> 6) & 0b11
    categories = ['P', 'C', 'B', 'U']
    category = categories[category_code]

    # Extract the first digit (bits 13 and 12)
    # Mask: 0b11 (3 in decimal)
    digit1 = (b1 >> 4) & 0b11
    
    # Extract the remaining 3 digits
    # Digit 2 (bits 11-8): Mask 0x0F
    digit2 = b1 & 0x0F 
    
    # Digit 3 (bits 7-4): Mask 0x0F
    digit3 = (b2 >> 4) & 0x0F
    
    # Digit 4 (bits 3-0): Mask 0x0F
    digit4 = b2 & 0x0F

    # Format the final DTC string using hexadecimal representation for the digits
    dtc_string = f"{category}{digit1:X}{digit2:X}{digit3:X}{digit4:X}"
    return dtc_string

def request_mil_status(bus):
    """
    Sends the Service 01 PID 01 request to get MIL status and reported DTC count.
    """
    # Request Message: 
    # ID: 0x7DF (Functional addressing)
    # Data: [0x02, 0x01, 0x01, 0x00, ...] (2 bytes of data: Service Mode 01, PID 01)
    request = can.Message(
        arbitration_id=OBD_REQUEST_ID,
        data=[0x02, SERVICE_MODE_01, PID_MIL_STATUS, 0x00, 0x00, 0x00, 0x00, 0x00],
        is_extended_id=False
    )

    print(f"\nSending MIL Status Request (Mode 01, PID 01): ID={hex(request.arbitration_id)}, Data={list(request.data)}")
    
    try:
        bus.send(request)
        
        timeout = 5.0
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            response = bus.recv(timeout=0.2)
            
            if response and response.arbitration_id == ECU_RESPONSE_ID:
                data = list(response.data)
                
                # Check for positive response (0x41) and correct PID (0x01)
                if len(data) < 4 or data[1] != RESPONSE_MODE_01 or data[2] != PID_MIL_STATUS:
                    # Ignore irrelevant or negative responses
                    continue 

                # Byte A (data[3]) contains the MIL status and DTC count
                byte_a = data[3]
                
                # MIL status is bit 7 (most significant bit) of Byte A
                mil_on = bool((byte_a >> 7) & 0b1)
                
                # DTC count is bits 0-6 of Byte A
                dtc_count = byte_a & 0x7F

                print("--- MIL STATUS RESPONSE RECEIVED (Mode 01, PID 01) ---")
                print(f"Raw Message: {response}")
                print(f"Check Engine Light (MIL) Status: {'ON' if mil_on else 'OFF'}")
                print(f"Reported Pending/Stored DTC Count: {dtc_count}")
                return

        print("\n Timeout: Did not receive MIL Status response.")

    except can.exceptions.CanOperationError as e:
        print(f"CAN Bus Error during MIL Status request: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during MIL Status request: {e}")

def request_dtcs(bus):
    """
    Sends the Service 03 request and processes the response.
    """
    # Request Message: 
    # ID: 0x7DF (Functional addressing)
    # Data: [0x02, 0x03, 0x00, 0x00, ...] (2 bytes of data: Service Mode 03)
    request = can.Message(
        arbitration_id=OBD_REQUEST_ID,
        data=[0x02, SERVICE_MODE_03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
        is_extended_id=False
    )

    print(f"Sending DTC Request (Mode 03): ID={hex(request.arbitration_id)}, Data={list(request.data)}\n")
    
    try:
        bus.send(request)
        
        # Wait for the response for up to 5 seconds
        timeout = 2.0
        start_time = time.time()
        
        # Use bus.recv() to wait for messages
        while (time.time() - start_time) < timeout:
            # Poll for new messages every 200ms
            response = bus.recv(timeout=0.05) 

            if response.arbitration_id >= 0x7e8 and response.arbitration_id <= 0x7ef:
                print(hex(response.arbitration_id))
            
            if response and (0x7e8 <= response.arbitration_id <= 0x7ef):
                print("--- DTC RESPONSE RECEIVED (Mode 03) ---")
                print(f"Raw Message: {response}")
                
                data = list(response.data)
                
                # Check for positive response (0x43)
                if len(data) < 2 or data[1] != RESPONSE_MODE_03:
                    print(f"Error: Received negative response or unexpected mode: {hex(data[1])}")
                    return

                # Get the actual data length from the first byte
                data_length = data[0]
                
                # DTC data starts at the 2nd index of the payload
                # Use data_length (if available) or the actual message length
                dtc_payload_end = data_length if data_length > 2 else len(data)
                dtc_payload = data[2:dtc_payload_end]
                
                # DTCs are 2 bytes each. Iterate and decode.
                if len(dtc_payload) % 2 != 0:
                    print("Warning: DTC payload length is odd. Data may be incomplete.")
                
                dtc_list = []
                for i in range(0, len(dtc_payload), 2):
                    dtc_bytes = dtc_payload[i:i+2]
                    if len(dtc_bytes) == 2:
                        dtc_code = decode_dtc(dtc_bytes)
                        dtc_list.append(dtc_code)

                if dtc_list:
                    print(f"\n✅ Found {len(dtc_list)} Stored DTCs:")
                    for dtc in dtc_list:
                        print(f" - {dtc}")
                else:
                    print("\n✅ ECU reports: No Stored DTCs found.")
                
                return

        print("\n Timeout: Did not receive a response from the ECU within 5 seconds.")

    except can.exceptions.CanOperationError as e:
        print(f"CAN Bus Error: Failed to send message. Is the interface configured and up? Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def main():
    # Initialize the CAN bus interface, prioritizing a real interface (e.g., SocketCAN 'can0')
    try:
        # NOTE: For actual hardware, you might need to change 'socketcan' and 'can0'
        # to match your setup (e.g., bustype='pcan', channel='PCAN_USBBUS1')
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        print("Connected to 'can0' (SocketCAN) - Ready to communicate with hardware.")
    except can.interface.BusError:
        # Fallback to the generic 'virtual' backend if the hardware interface is not found
        bus = can.interface.Bus(channel='virtual', bustype='virtual')
        print("Warning: Could not connect to 'can0'. Using 'virtual' bus (In-memory simulation) instead.")

    print("\nStarting diagnostic requests...")
 
    # Run the DTC request logic (Mode 03)
    request_dtcs(bus)

    # Run the MIL status request (Mode 01 PID 01)
    request_mil_status(bus)
    
   
    # Clean up the bus
    bus.shutdown()
    print("\nBus connection closed.")

if __name__ == "__main__":
    main()
