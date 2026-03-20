/// Entry point for the smcwrite privileged helper daemon.
import Foundation
import SMCWriteLib

let socketPath = "/var/run/macfancontrol.sock"

func log(_ msg: String) {
    let ts = ISO8601DateFormatter().string(from: Date())
    FileHandle.standardError.write(Data("[\(ts)] \(msg)\n".utf8))
}

signal(SIGTERM) { _ in
    unlink(socketPath)
    exit(0)
}
signal(SIGINT) { _ in
    unlink(socketPath)
    exit(0)
}

log("macfancontrol smcwrite helper starting (pid=\(getpid()))")

let driver = SMCDriver()
let handler = CommandHandler(driver: driver)
let server = SocketServer(path: socketPath, handler: handler)
server.start()
