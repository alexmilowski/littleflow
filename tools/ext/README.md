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

Once the `vsce` command completes, a file with a vsix extension (e.g., `littleflow-language-0.0.2.vsix`) should have been created.

## Install

Once you have the `.vsix` file, just go to "Preferences > Extension" and click on the "..." in the upper right of the panel. Then select "Install from VSIX ..."

The extension should show up in the list of installed extensions.  If so, you should see the syntax highlighting when opening a ".flow" file.