import sys
from pathlib import Path

import grpc_tools
from grpc_tools import protoc

proto_dir = Path(sys.argv[1]).resolve()
output_dir = Path(sys.argv[2]).resolve()
raise SystemExit(
    protoc.main(
        [
            "protoc",
            f"-I{proto_dir}",
            f"-I{Path(grpc_tools.__file__).parent / '_proto'}",
            f"--python_out={output_dir}",
            f"--grpc_python_out={output_dir}",
            str(proto_dir / "contracts/flight.proto"),
        ]
    )
)
