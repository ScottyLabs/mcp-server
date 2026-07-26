{
  description = "Scotty Labs MCPs for CMU";
  nixConfig = {
    extra-substituters = [ "https://scottylabs.cachix.org" ];
    extra-trusted-public-keys = [
      "scottylabs.cachix.org-1:hajjEX5SLi/Y7yYloiXTt2IOr3towcTGRhMh1vu6Tjg="
    ];
  };
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    scottylabs = {
      url = "git+https://codeberg.org/ScottyLabs/kennel";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      scottylabs,
      ...
    }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in

    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          venv = (scottylabs.mkLib pkgs).buildPythonService {
            src = ./.;
            python = pkgs.python313;
          };
          api = pkgs.runCommand "mcp-server-api" { meta.mainProgram = "mcp-server"; } ''
            mkdir -p $out/bin
            ln -s ${venv}/bin/mcp-server $out/bin/mcp-server
          '';
        in
        {
          inherit api;
          default = api;
        }
      );
    };
}
