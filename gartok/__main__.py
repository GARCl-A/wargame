"""`python -m gartok`: the game in a browser window (`gartok.web`). The Editor is a separate program
(`python -m editor`); the game never imports it."""


def main():
    from .web.__main__ import main as web
    web()


if __name__ == "__main__":
    main()
