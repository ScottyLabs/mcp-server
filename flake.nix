{
  description = "Scotty Labs MCPs for CMU";

  nixConfig = {
    extra-substituters = [ "https://scottylabs.cachix.org" ];
    extra-trusted-public-keys = [
      "scottylabs.cachix.org-1:hajjEX5SLi/Y7yYloiXTt2IOr3towcTGRhMh1vu6Tjg="
    ];
  };

  inputs = {
    scottylabs.url = "git+https://git.cmu.dev/ScottyLabs/kennel";
    nixpkgs.follows = "scottylabs/nixpkgs";
    flake-parts.follows = "scottylabs/flake-parts";
  };

  outputs =
    inputs:
    inputs.flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [ inputs.scottylabs.flakeModules.default ];
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      perSystem =
        {
          pkgs,
          lib,
          helpers,
          ...
        }:
        {
          scottylabs = {
            project.name = "mcp-server";

            python = {
              enable = true;
              package = pkgs.python313;
            };

            processes.api = {
              run = "PORT=5050 exec uv run python src/mcp_server/main.py";
              ready = "${lib.getExe pkgs.curl} -sf http://localhost:5050/api/health";
            };
          };

          services.api = {
            package = lib.addMetaAttrs { mainProgram = "mcp-server"; } (
              helpers.buildPythonService {
                src = ./.;
                python = pkgs.python313;
              }
            );
            customDomain = "api.mcp-server.scottylabs.org";
          };
        };
    };
}
