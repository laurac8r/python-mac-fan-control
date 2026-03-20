import Foundation

/// Convert a hex string to an array of bytes.
///
/// - Parameter hex: An even-length string of hex characters (e.g. "00409c45").
/// - Returns: Array of decoded bytes, or nil if the input is invalid.
public func hexToBytes(_ hex: String) -> [UInt8]? {
    let chars = Array(hex)
    guard chars.count % 2 == 0 else { return nil }
    var result = [UInt8]()
    result.reserveCapacity(chars.count / 2)
    for i in stride(from: 0, to: chars.count, by: 2) {
        guard let byte = UInt8(String(chars[i...i+1]), radix: 16) else { return nil }
        result.append(byte)
    }
    return result
}

/// Convert an array of bytes to a lowercase hex string.
///
/// - Parameter bytes: Raw byte array.
/// - Returns: Hex-encoded string (e.g. "00409c45").
public func bytesToHex(_ bytes: [UInt8]) -> String {
    bytes.map { String(format: "%02x", $0) }.joined()
}
