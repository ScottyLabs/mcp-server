{
  inputs,
  ...
}:

{
  imports = [ inputs.scottylabs.devenvModules.default ];

  scottylabs = {
    enable = true;
    project.name = "mcp-server";

    kennel.services.api = {
      customDomain = "api.mcp-server.scottylabs.org";
    };
  };

  processes.api = {
    exec = "uv run python src/mcp_server/main.py"; # "secretspec run --profile dev -- uv run python src/mcp_server/main.py";
    env.PORT = "5050";
    ready.http.get = {
      port = 5050;
      path = "/health";
    };
  };
}
