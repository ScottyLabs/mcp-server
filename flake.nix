{
    description = "Scotty Labs MCPs for CMU";

    inputs = {
        nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
    };

    outputs = { self, nixpkgs }:
    let
        inherit (nixpkgs) lib;
        systems = [
            "aarch64-linux"
            "x86_64-linux"
            "aarch64-darwin"
            "x86_64-darwin"
        ];
        forAllSystems = f: lib.genAttrs systems f;
    in
    {
        packages = forAllSystems (system:
            let
                pkgs = nixpkgs.legacyPackages.${system};
                python = pkgs.python311;
            in
            {
                default = python.pkgs.buildPythonApplication {
                    pname = "mcp-server";
                    version = "0.1.0";
                    pyproject = true;
                    src = ./.;
                    nativeBuildInputs = with python.pkgs; [ uv-build ];
                    propagatedBuildInputs = with python.pkgs; [ fastmcp aiohttp ];
                    pythonImportsCheck = [ "mcp_server" ];
                };
            }
        );

        devShells = forAllSystems (system:
            let pkgs = nixpkgs.legacyPackages.${system};
            in {
                default = pkgs.mkShell {
                    packages = [
                        pkgs.python311
                        pkgs.uv
                    ];
                };
            }
        );

        nixosModules.default = import ./nix/module.nix { inherit self; };
        nixosModules.mcp-server = self.nixosModules.default;
    };
}
