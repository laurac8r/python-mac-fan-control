import Foundation

/// Parse a single JSON line into a dictionary.
///
/// - Parameter line: A JSON string (without trailing newline).
/// - Returns: Parsed dictionary, or nil if invalid.
public func parseJSONLine(_ line: String) -> [String: Any]? {
    guard !line.isEmpty,
          let data = line.data(using: .utf8),
          let obj = try? JSONSerialization.jsonObject(with: data),
          let dict = obj as? [String: Any]
    else { return nil }
    return dict
}

/// Serialize a response dictionary to a newline-terminated JSON string.
///
/// - Parameter response: Dictionary to serialize.
/// - Returns: JSON string with trailing newline.
public func serializeResponse(_ response: [String: Any]) -> String {
    guard let data = try? JSONSerialization.data(withJSONObject: response),
          let str = String(data: data, encoding: .utf8)
    else { return "{\"ok\":false,\"error\":\"serialize failed\"}\n" }
    return str + "\n"
}

/// Unix domain socket server that dispatches JSON commands to a CommandHandler.
public final class SocketServer {
    private let path: String
    private let handler: CommandHandler
    private var serverFd: Int32 = -1
    private var running = false

    public init(path: String, handler: CommandHandler) {
        self.path = path
        self.handler = handler
    }

    /// Start listening. Blocks the calling thread.
    public func start() {
        unlink(path)

        serverFd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard serverFd >= 0 else { return }

        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        path.withCString { ptr in
            withUnsafeMutablePointer(to: &addr.sun_path) { pathPtr in
                pathPtr.withMemoryRebound(to: CChar.self, capacity: 104) { dest in
                    _ = strcpy(dest, ptr)
                }
            }
        }

        let bindResult = withUnsafePointer(to: &addr) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
                bind(serverFd, sockPtr, socklen_t(MemoryLayout<sockaddr_un>.size))
            }
        }
        guard bindResult == 0 else { return }

        chmod(path, 0o666)
        guard listen(serverFd, 5) == 0 else { return }

        running = true

        while running {
            var clientAddr = sockaddr_un()
            var clientLen = socklen_t(MemoryLayout<sockaddr_un>.size)
            let clientFd = withUnsafeMutablePointer(to: &clientAddr) { ptr in
                ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
                    accept(serverFd, sockPtr, &clientLen)
                }
            }
            guard clientFd >= 0 else { continue }

            Thread.detachNewThread { [handler] in
                Self.handleClient(clientFd, handler: handler)
            }
        }
    }

    /// Signal the server to stop accepting connections.
    public func stop() {
        running = false
        if serverFd >= 0 {
            Darwin.close(serverFd)
            serverFd = -1
        }
        unlink(path)
    }

    private static func handleClient(_ fd: Int32, handler: CommandHandler) {
        let bufSize = 4096
        var accumulated = ""

        while true {
            var buf = [UInt8](repeating: 0, count: bufSize)
            let n = read(fd, &buf, bufSize)
            if n <= 0 { break }

            accumulated += String(bytes: buf[0..<n], encoding: .utf8) ?? ""

            while let range = accumulated.range(of: "\n") {
                let line = String(accumulated[accumulated.startIndex..<range.lowerBound])
                accumulated = String(accumulated[range.upperBound...])

                guard !line.isEmpty else { continue }

                let response: [String: Any]
                if let json = parseJSONLine(line) {
                    response = handler.handle(json)
                } else {
                    response = ["ok": false, "error": "Invalid JSON"]
                }

                let reply = serializeResponse(response)
                _ = reply.withCString { write(fd, $0, strlen($0)) }
            }
        }

        Darwin.close(fd)
    }
}
