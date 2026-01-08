mkdir -p .devcontainer

cat <<'EOL' > .devcontainer/devcontainer.json
{
  "name": "My Codespace",
  "image": "mcr.microsoft.com/vscode/devcontainers/python:3.8",
  "postStartCommand": "python3 /workspaces/new/m.py",
  "customizations": {
    "vscode": {
      "settings": {
        "python.pythonPath": "/usr/local/bin/python3"
      },
      "extensions": [
        "ms-python.python"
      ]
    }
  }
}
EOL

