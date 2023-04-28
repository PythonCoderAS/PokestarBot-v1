import os

import jinja2
import markdown
import pymdownx.emoji

md = markdown.Markdown(extensions=[
    'pymdownx.emoji',
    "sane_lists",
    "smarty",
    "pymdownx.inlinehilite",
    "admonition",
    "codehilite",
    "pymdownx.superfences",
    "tables",
    "md_in_html",
    "pymdownx.tabbed",
    "pymdownx.keys",
    "pymdownx.betterem",
    "toc"
],
    extension_configs={
        "pymdownx.emoji": {
            "emoji_index": pymdownx.emoji.twemoji,
            "emoji_generator": pymdownx.emoji.to_svg
        },

    }
)

env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.abspath(os.path.join(__file__, ".."))))
template = env.get_template("template.html")

def format_parts(parts: list):
    """Format a parts list to be prettified"""
    for i in range(len(parts)):
        if "_" in parts[i]:
            parts[i] = parts[i].replace("_", " ")

def do_file(file_name, current_dir, export_dir, content_path):
    with open(os.path.join(current_dir, file_name), "r") as fp:
        data = fp.read()
    lines = data.splitlines(False)
    title = lines[0]
    parts = [item for item in current_dir.replace(content_path, "").split("/") if item] + [title]
    if os.path.splitext(file_name)[0] == "index" and len(parts) > 1:
        parts.pop(-2)
    content = md.convert(os.linesep.join(lines[1:]))
    toc = getattr(md, "toc", None)
    rendered = template.render(title=title, content=content, page_parts=parts,
                               toc=None if toc == '<div class="toc">\n<ul></ul>\n</div>\n' else toc)
    with open(os.path.join(export_dir, os.path.splitext(file_name)[0] + ".html"), "w") as fp:
        fp.write(rendered)
    md.reset()

def main():
    content_path = os.path.abspath(os.path.join(__file__, "..", "data", "markdown"))
    export_path = os.path.abspath(os.path.join(__file__, "..", "data", "html"))
    os.makedirs(export_path, exist_ok=True)
    for cd, folders, files in os.walk(content_path):
        ecd = cd.replace(content_path, export_path)
        os.makedirs(ecd, exist_ok=True)
        for file in files:
            do_file(file, cd, ecd, content_path)

if __name__ == '__main__':
    main()
