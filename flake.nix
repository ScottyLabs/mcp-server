{
    description = "Scotty Labs MCPs for CMU";

    inputs = {
        nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
    };

    outputs = { self, nixpkgs }:
    let
        supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
        forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in
    {
        nixosModules.default = import ./nix/module.nix { inherit self; };
        nixosModules.mcp-server = self.nixosModules.default;

        devShells = forAllSystems (system:
            let pkgs = nixpkgs.legacyPackages.${system};
            in {
                default = pkgs.mkShell {
                    buildInputs = [
                        pkgs.python311
                        pkgs.uv
                    ];
                };
            }
        );
    };
}
