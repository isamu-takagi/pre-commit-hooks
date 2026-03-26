import pathlib
import re
import xml.etree.ElementTree as etree


class RosPackageXml:
    def __init__(self, path: pathlib.Path):
        self._tree = etree.parse(path)
        self._root = self._tree.getroot()

    def get_name(self, include_prefix=True):
        name = self._root.find("name").text
        return name if include_prefix else name.removeprefix("autoware_")

    def list_package_depends(self):
        pkgs = set()
        for node in self._root:
            if node.tag.endswith("depend") or node.tag == "name":
                pkgs.add(node.text)
        return pkgs


class RosPackageXmlEdit:

    class Line:
        def __init__(self, text=None, type=None):
            self.text = text
            self.type = type  # depend type or text if empty
            self.pkgs = set()

    @staticmethod
    def _first_depend_match_outside_comment(pattern, line: str):
        """Skip matches whose opening '<' starts an XML comment (<!--)."""
        for m in pattern.finditer(line):
            if line[m.start() : m.start() + 4] == "<!--":
                continue
            return m
        return None

    def __init__(self, path: pathlib.Path):
        self._path = path
        self._depends = {}
        self._content = []

        pattern = re.compile(r"<(.*?depend)>(.*?)</.*?depend>")
        lines = path.read_text().split("\n")
        for line in lines:
            match = self._first_depend_match_outside_comment(pattern, line)
            if not match:
                self._content.append(self.Line(text=line))
                continue
            tag = match.group(1)
            pkg = match.group(2)
            if tag not in self._depends:
                self._content.append(self.Line(type=tag))
                self._depends[tag] = self._content[-1]
            self._depends[tag].pkgs.add(pkg)

    def write(self):
        lines = []
        for line in self._content:
            if line.type is None:
                lines.append(line.text)
            else:
                for pkg in sorted(line.pkgs):
                    lines.append(f"  <{line.type}>{pkg}</{line.type}>")
        self._path.write_text("\n".join(lines))

    def add_depend(self, tag: str, pkgs: str | list[str]):
        pkgs = [pkgs] if pkgs is str else pkgs
        for pkg in pkgs:
            if tag not in self._depends:
                self.__insert_new_depend(tag)
            self._depends[tag].pkgs.add(pkg)

    def __insert_new_depend(self, tag):
        order = [
            "buildtool_depend",
            "buildtool_export_depend",
            "depend",
            "build_depend",
            "build_export_depend",
            "exec_depend",
            "test_depend",
        ]
        index = order.index(tag)
        max_i = 0
        for i, line in enumerate(self._content):
            for j in range(index):
                if line.type == order[j]:
                    max_i = max(max_i, i)
        self._content.insert(max_i + 1, self.Line(type=tag))
        self._content.insert(max_i + 1, self.Line(text=""))
        self._depends[tag] = self._content[max_i + 2]
