import XCTest
@testable import SMCWriteLib
import Foundation

final class SocketServerTests: XCTestCase {

    var tempSocketPath: String!

    override func setUp() {
        super.setUp()
        tempSocketPath = NSTemporaryDirectory() + "test_smcwrite_\(UUID().uuidString).sock"
    }

    override func tearDown() {
        unlink(tempSocketPath)
        super.tearDown()
    }

    // MARK: - parseJSONLine

    func testParseValidJSON() {
        let result = parseJSONLine("{\"cmd\":\"ping\"}")
        XCTAssertEqual(result?["cmd"] as? String, "ping")
    }

    func testParseEmptyStringReturnsNil() {
        XCTAssertNil(parseJSONLine(""))
    }

    func testParseInvalidJSONReturnsNil() {
        XCTAssertNil(parseJSONLine("not json"))
    }

    func testParseArrayReturnsNil() {
        XCTAssertNil(parseJSONLine("[1,2,3]"))
    }

    // MARK: - serializeResponse

    func testSerializeOk() {
        let json = serializeResponse(["ok": true])
        XCTAssertTrue(json.hasSuffix("\n"))
        XCTAssertTrue(json.contains("\"ok\""))
    }

    func testSerializeWithError() {
        let json = serializeResponse(["ok": false, "error": "test"])
        XCTAssertTrue(json.contains("test"))
    }

    // MARK: - End-to-end socket communication

    func testSocketRoundTrip() throws {
        let mock = MockSMCDriver()
        let handler = CommandHandler(driver: mock)
        let server = SocketServer(path: tempSocketPath, handler: handler)

        // Start server in background
        let serverThread = Thread {
            server.start()
        }
        serverThread.start()

        // Give server time to bind
        Thread.sleep(forTimeInterval: 0.2)

        // Connect as client
        let clientFd = socket(AF_UNIX, SOCK_STREAM, 0)
        XCTAssertGreaterThan(clientFd, 0)

        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        tempSocketPath.withCString { ptr in
            withUnsafeMutablePointer(to: &addr.sun_path) { pathPtr in
                pathPtr.withMemoryRebound(to: CChar.self, capacity: 104) { dest in
                    _ = strcpy(dest, ptr)
                }
            }
        }
        let connectResult = withUnsafePointer(to: &addr) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
                connect(clientFd, sockPtr, socklen_t(MemoryLayout<sockaddr_un>.size))
            }
        }
        XCTAssertEqual(connectResult, 0, "Connect failed: \(String(cString: strerror(errno)))")

        // Send ping
        let msg = "{\"cmd\":\"ping\"}\n"
        _ = msg.withCString { write(clientFd, $0, strlen($0)) }

        // Read response
        var buf = [UInt8](repeating: 0, count: 4096)
        let n = read(clientFd, &buf, buf.count)
        XCTAssertGreaterThan(n, 0)

        let response = String(bytes: buf[0..<n], encoding: .utf8) ?? ""
        XCTAssertTrue(response.contains("\"ok\""))
        XCTAssertTrue(response.contains("true"))

        Darwin.close(clientFd)
        server.stop()
    }

    func testSocketWriteCommand() throws {
        let mock = MockSMCDriver()
        let handler = CommandHandler(driver: mock)
        let server = SocketServer(path: tempSocketPath, handler: handler)

        let serverThread = Thread {
            server.start()
        }
        serverThread.start()
        Thread.sleep(forTimeInterval: 0.2)

        let clientFd = socket(AF_UNIX, SOCK_STREAM, 0)
        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        tempSocketPath.withCString { ptr in
            withUnsafeMutablePointer(to: &addr.sun_path) { pathPtr in
                pathPtr.withMemoryRebound(to: CChar.self, capacity: 104) { dest in
                    _ = strcpy(dest, ptr)
                }
            }
        }
        _ = withUnsafePointer(to: &addr) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
                connect(clientFd, sockPtr, socklen_t(MemoryLayout<sockaddr_un>.size))
            }
        }

        // Open, write, close sequence
        let commands = [
            "{\"cmd\":\"open\"}\n",
            "{\"cmd\":\"write\",\"key\":\"F0Mn\",\"data\":\"00409c45\"}\n",
            "{\"cmd\":\"close\"}\n",
        ]

        for cmd in commands {
            _ = cmd.withCString { write(clientFd, $0, strlen($0)) }
            var buf = [UInt8](repeating: 0, count: 4096)
            _ = read(clientFd, &buf, buf.count)
        }

        XCTAssertEqual(mock.openCallCount, 1)
        XCTAssertEqual(mock.writeCallCount, 1)
        XCTAssertEqual(mock.lastWriteKey, "F0Mn")
        XCTAssertEqual(mock.lastWriteData, [0x00, 0x40, 0x9c, 0x45])
        XCTAssertEqual(mock.closeCallCount, 1)

        Darwin.close(clientFd)
        server.stop()
    }
}
