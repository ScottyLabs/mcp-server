{ pkgs, lib, config, inputs, ... }:

{
  imports = [ inputs.scottylabs.devenvModules.default ];

  scottylabs = {
    enable = true;
    project.name = "mcp-server";
    secrets.enable = true;

    kennel.services.api = {
      customDomain = "api.mcp-server.scottylabs.org";
    };
  };


  cachix.enable = false;

  languages.python = {
    enable = true;
    package = pkgs.python311;
    poetry.enable = true;
    uv.enable = true;
  };

  processes.api = {
    exec = "secretspec run --profile dev -- uv run python src/mcp_server/main.py";
    env.PORT = "5050";
    ready.http.get = { port = 5050; path = "/health"; };
  };

  enterShell = ''
    [ -f .env ] || touch .env
  '';

  env.VAULT_ADDR = "https://secrets2.scottylabs.org";

}


  

 
