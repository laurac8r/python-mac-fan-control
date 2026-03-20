import Foundation

/// Handles JSON command dictionaries and dispatches to the SMC driver.
public final class CommandHandler {
    private let driver: SMCDriverProtocol

    public init(driver: SMCDriverProtocol) {
        self.driver = driver
    }

    /// Process a single command dictionary and return a response dictionary.
    ///
    /// - Parameter json: Dictionary with at least a "cmd" key.
    /// - Returns: Response dictionary with "ok" bool and optional "error"/"data".
    public func handle(_ json: [String: Any]) -> [String: Any] {
        guard let cmd = json["cmd"] as? String else {
            return ["ok": false, "error": "Missing 'cmd' field"]
        }

        switch cmd {
        case "ping":
            return ["ok": true, "version": "1.0.0"]

        case "open":
            let kr = driver.open()
            if kr == 0 {
                return ["ok": true]
            }
            return ["ok": false, "error": "SMCOpen failed (kr=\(kr))"]

        case "close":
            driver.close()
            return ["ok": true]

        case "write":
            guard driver.isOpen else {
                return ["ok": false, "error": "SMC connection is not open"]
            }
            guard let key = json["key"] as? String, key.count == 4 else {
                return ["ok": false, "error": "Missing or invalid 'key'"]
            }
            guard let hexData = json["data"] as? String else {
                return ["ok": false, "error": "Missing 'data' (hex string)"]
            }
            guard let dataBytes = hexToBytes(hexData) else {
                return ["ok": false, "error": "Invalid hex in 'data'"]
            }
            let kr = driver.writeKey(key, data: dataBytes)
            if kr == 0 {
                return ["ok": true]
            }
            return ["ok": false, "error": "SMCWriteKey '\(key)' failed (kr=\(kr))"]

        case "read":
            guard driver.isOpen else {
                return ["ok": false, "error": "SMC connection is not open"]
            }
            guard let key = json["key"] as? String, key.count == 4 else {
                return ["ok": false, "error": "Missing or invalid 'key'"]
            }
            let (bytes, kr) = driver.readKey(key)
            if kr == 0 {
                return ["ok": true, "data": bytesToHex(bytes)]
            }
            return ["ok": false, "error": "SMCReadKey '\(key)' failed (kr=\(kr))"]

        default:
            return ["ok": false, "error": "Unknown command '\(cmd)'"]
        }
    }
}
