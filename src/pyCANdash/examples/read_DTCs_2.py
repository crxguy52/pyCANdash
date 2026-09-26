import can
import time
import isotp # Required for robust ISO-TP (multi-frame) handling

# --- Constants for OBD-II Communication ---
# Functional ID for requesting diagnostics from all ECUs (11-bit)
OBD_REQUEST_ID = 0x7DF 

# OBD-II response range (0x7E8 to 0x7EF)
RESPONSE_ID_BASE = 0x7E8
RESPONSE_ID_MAX = 0x7EF

# Service Mode 01 and 03 constants remain the same
SERVICE_MODE_01 = 0x01
PID_MIL_STATUS = 0x01
RESPONSE_MODE_01 = 0x41 
SERVICE_MODE_03 = 0x03
RESPONSE_MODE_03 = 0x43 
NEGATIVE_RESPONSE_ID = 0x7F 

# --- Utility Functions ---

def is_obd_response(arb_id):
    """Checks if the arbitration ID is within the standard OBD-II response range."""
    return RESPONSE_ID_BASE <= arb_id <= RESPONSE_ID_MAX

def get_physical_request_id(response_id):
    """Calculates the physical request ID (Tx ID) based on the response ID (Rx ID).
    Standard: Rx_ID - 8 = Tx_ID (e.g., 0x7E8 - 8 = 0x7E0)."""
    return response_id - 0x8 

def decode_dtc(dtc_bytes):
    """
    Decodes a 2-byte hexadecimal DTC value into the standard 5-character P/C/B/U format.
    """
    if len(dtc_bytes) != 2:
        return f"Invalid DTC length ({len(dtc_bytes)})"

    b1 = dtc_bytes[0]
    b2 = dtc_bytes[1]

    # Map the first two bits (15 and 14) to the DTC category
    category_code = (b1 >> 6) & 0b11
    categories = ['P', 'C', 'B', 'U']
    category = categories[category_code]

    # Extract the first digit (bits 13 and 12)
    digit1 = (b1 >> 4) & 0b11
    
    # Extract the remaining 3 digits
    digit2 = b1 & 0x0F 
    digit3 = (b2 >> 4) & 0x0F
    digit4 = b2 & 0x0F

    # Format the final DTC string using hexadecimal representation for the digits
    dtc_string = f"{category}{digit1:X}{digit2:X}{digit3:X}{digit4:X}"
    return dtc_string

# --- Request Functions ---

def request_mil_status(bus):
    """
    Sends the Service 01 PID 01 request (Single Frame) to get MIL status and DTC count.
    Returns: tuple (dtc_count, ecu_response_id) or (None, None) on failure/timeout.
    """
    request = can.Message(
        arbitration_id=OBD_REQUEST_ID,
        data=[0x02, SERVICE_MODE_01, PID_MIL_STATUS, 0x00, 0x00, 0x00, 0x00, 0x00],
        is_extended_id=False
    )

    print(f"\nSending MIL Status Request (Mode 01, PID 01): ID={hex(request.arbitration_id)}, Data={list(request.data)}")
    
    try:
        bus.send(request)
        timeout = 6.0 
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            response = bus.recv(timeout=0.2)
            
            if response and is_obd_response(response.arbitration_id):
                data = list(response.data)
                
                # Check for positive response (0x41) and correct PID (0x01)
                if len(data) < 4 or data[1] != RESPONSE_MODE_01 or data[2] != PID_MIL_STATUS:
                    if len(data) >= 3 and data[1] == NEGATIVE_RESPONSE_ID and data[2] == SERVICE_MODE_01:
                        print(f"--- NEGATIVE RESPONSE (Mode 01) RECEIVED ---")
                        print(f"ECU ID: {hex(response.arbitration_id)}, Raw Data: {data}")
                        return None, response.arbitration_id
                    continue 

                # Process successful response
                byte_a = data[3]
                mil_on = bool((byte_a >> 7) & 0b1)
                dtc_count = byte_a & 0x7F

                print("--- MIL STATUS RESPONSE RECEIVED (Mode 01, PID 01) ---")
                print(f"Raw Message ID: {hex(response.arbitration_id)}")
                print(f"Check Engine Light (MIL) Status: {'ON' if mil_on else 'OFF'}")
                print(f"Reported Pending/Stored DTC Count: {dtc_count}")
                # Return count and the response ID of the active ECU
                return dtc_count, response.arbitration_id

        print("\n❌ Timeout: Did not receive MIL Status response.")
        return None, None

    except Exception as e:
        print(f"An error occurred during MIL Status request: {e}")
        return None, None


def request_dtcs_isotp(bus, ecu_response_id):
    """
    Requests DTCs using ISO-TP (multi-frame) connection to handle large payloads.
    Uses isotp.CanStack to avoid dependency on the 'client' submodule.
    """
    ecu_request_id = get_physical_request_id(ecu_response_id)
    
    print(f"\n** Setting up ISO-TP Connection for multi-frame read **")
    print(f"Tx ID (Client to ECU): {hex(ecu_request_id)} | Rx ID (ECU to Client): {hex(ecu_response_id)}")
    
    try:
        # Using the more general 'isotp.CanStack' object
        conn = isotp.CanStack(
            bus=bus,
            address=isotp.Address(
                txid=ecu_request_id,
                rxid=ecu_response_id,
            )
        )
    except Exception as e:
        print(f"❌ Failed to set up isotp.CanStack. Error: {e}")
        print("Please verify your 'isotp' package installation.")
        return

    # Mode 03 request payload (03)
    request_payload = bytearray([SERVICE_MODE_03])
    
    print(f"\nSending ISO-TP DTC Request (Mode 03: {list(request_payload)})")

    try:
        # Send the payload via the ISO-TP connection
        conn.send(request_payload)
        
        # Receive the full, reassembled payload (Mode 03 response)
        # Timeout set higher for a multi-frame operation
        response_payload = conn.recv(timeout=10.0) 
        
        if response_payload is None:
            print("❌ Timeout: Did not receive a complete ISO-TP response for Mode 03.")
            print("This could happen if the ECU is silent, or if the initial FF was missed.")
            return

        # Response payload is a bytearray: [0x43, DTC_MSB_1, DTC_LSB_1, DTC_MSB_2, DTC_LSB_2, ...]
        response_mode = response_payload[0]
        
        if response_mode == NEGATIVE_RESPONSE_ID:
             print(f"🛑 NEGATIVE RESPONSE RECEIVED: {hex(response_payload[2])} for Mode {hex(response_payload[1])}")
             return

        if response_mode != RESPONSE_MODE_03:
            print(f"Error: Received unexpected response mode: {hex(response_mode)}")
            return

        # DTC data starts at the 1st index of the payload
        dtc_payload = response_payload[1:] 
        
        dtc_list = []
        for i in range(0, len(dtc_payload), 2):
            dtc_bytes = dtc_payload[i:i+2]
            if len(dtc_bytes) == 2:
                dtc_code = decode_dtc(dtc_bytes)
                dtc_list.append(dtc_code)

        if dtc_list:
            print(f"\n✅ ISO-TP Success! Found {len(dtc_list)} Stored DTCs:")
            for dtc in dtc_list:
                print(f" - {dtc}")
        else:
            print("\n✅ ECU reports: No Stored DTCs found (Payload 0x43 followed by no data).")
            
    except can.exceptions.CanOperationError as e:
        print(f"CAN Bus Error during ISO-TP transaction: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during ISO-TP transaction: {e}")


def main():
    # Initialize the CAN bus interface
    try:
        # FIX: Replaced 'bustype' with 'interface' to avoid DeprecationWarning
        bus = can.interface.Bus(channel='can0', interface='socketcan')
        print("Connected to 'can0' (SocketCAN) - Ready to communicate with hardware.")
    except Exception:
        # FIX: Replaced 'bustype' with 'interface' for the virtual fallback
        bus = can.interface.Bus(channel='virtual', interface='virtual')
        print("Warning: Could not connect to 'can0'. Using 'virtual' bus (In-memory simulation) instead.")

    print("\nStarting diagnostic requests...")
    
    # 1. Run the MIL status request first (Mode 01 PID 01)
    dtc_count, ecu_id = request_mil_status(bus)
    
    if ecu_id is None:
        print("\n🛑 Cannot proceed: Failed to establish communication with the ECU.")
    elif dtc_count is not None and dtc_count > 0:
        print(f"\n** DTCs Reported in Mode 01 ({dtc_count} codes). Switching to ISO-TP for full read... **")
        # 2. Run the DTC request logic (Mode 03) using ISO-TP
        request_dtcs_isotp(bus, ecu_id)
    else:
        print(f"\n💡 DIAGNOSIS: The ECU reported **0 stored DTCs** via Mode 01.")
        print("Mode 03 is being skipped as the ECU is likely silent when no codes are present.")
    
    # Clean up the bus
    bus.shutdown()
    print("\nBus connection closed.")

if __name__ == "__main__":
    main()
