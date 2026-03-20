// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SMCWriteHelper",
    platforms: [.macOS(.v13)],
    targets: [
        .target(
            name: "SMCWriteLib",
            path: "Sources/SMCWriteLib"
        ),
        .executableTarget(
            name: "smcwrite",
            dependencies: ["SMCWriteLib"],
            path: "Sources/smcwrite",
            linkerSettings: [
                .linkedFramework("IOKit"),
            ]
        ),
        .testTarget(
            name: "SMCWriteLibTests",
            dependencies: ["SMCWriteLib"],
            path: "Tests/SMCWriteLibTests"
        ),
    ]
)
