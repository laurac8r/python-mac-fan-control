import Foundation

/// Convert a 4-character SMC key string to a UInt32.
///
/// - Parameter s: A 4-character ASCII string (e.g. "F0Mn").
/// - Returns: The big-endian UInt32 representation.
public func fourCharCode(_ s: String) -> UInt32 {
    var result: UInt32 = 0
    for c in s.utf8.prefix(4) {
        result = (result << 8) | UInt32(c)
    }
    return result
}

/// Convert a UInt32 back to a 4-character SMC key string.
///
/// - Parameter v: A big-endian UInt32 key code.
/// - Returns: The 4-character ASCII string.
public func uint32ToString(_ v: UInt32) -> String {
    let bytes: [UInt8] = [
        UInt8((v >> 24) & 0xFF),
        UInt8((v >> 16) & 0xFF),
        UInt8((v >> 8) & 0xFF),
        UInt8(v & 0xFF),
    ]
    return String(bytes: bytes, encoding: .ascii) ?? "????"
}
