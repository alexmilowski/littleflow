# Developing the extension

## Testing

There is an integration with VSCode in the root of this project. With that, you should have "Run Extension" available in "Run and Debug". Using
that will start a new version of VSCode with this extension code. 

## Packaging

You'll need this tool:

```
npm install -g @vscode/vsce
```

Then you run this command in this directory:

```
vsce package
```