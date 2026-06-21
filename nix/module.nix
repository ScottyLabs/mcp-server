{ self }:
{ config, pkgs, lib, ... }:

let
    cfg = config.services.mcpServer;
    pkgForSystem = self.packages.${pkgs.stdenv.hostPlatform.system}.default or null;
in
{
    options.services.mcpServer = {
        enable = lib.mkEnableOption "Scotty Labs MCP server (FastMCP)";

        package = lib.mkOption {
            type = lib.types.nullOr lib.types.package;
            default = pkgForSystem;
            description = "mcp-server package; defaults to this flake's build for the host platform.";
        };
    };

    config = lib.mkIf cfg.enable {
        assertions = [
            {
                assertion = cfg.package != null;
                message = "mcp-server: no package output for ${pkgs.stdenv.hostPlatform.system}; override services.mcpServer.package.";
            }
        ];

        systemd.services.mcp-server = {
            description = "Scotty Labs MCP server";
            after = [ "network.target" ];
            wantedBy = [ "multi-user.target" ];
            serviceConfig = {
                ExecStart = lib.getExe cfg.package;
                Restart = "on-failure";
                DynamicUser = true;
            };
        };
    };
}
