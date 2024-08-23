let
  pkgs = import <nixpkgs> { };
in
  pkgs.mkShell {
    packages = [
      pkgs.python3Packages.html2text
      pkgs.python3Packages.beautifulsoup4
      pkgs.python3Packages.requests
      pkgs.python3Packages.unidecode
      pkgs.python3Packages.pudb
    ];
  }
