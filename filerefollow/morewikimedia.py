#!/usr/bin/env python
'''
Convert all downloaded HTML files from WikiMedia Commons into the files to which they point.

Example:
produces an HTML file. It will have links such as:
<audio id="mwe_player_0" controls="" preload="none" width="300" style="width:300px;" data-durationhint="9" data-mwtitle="2-3_guajeo.mid" data-mwprovider="local">
<source src="https://upload.wikimedia.org/wikipedia/commons/transcoded/a/a7/2-3_guajeo.mid/2-3_guajeo.mid.mp3" type="audio/mpeg" data-transcodekey="mp3" data-width="0" data-height="0">
<source src="https://upload.wikimedia.org/wikipedia/commons/transcoded/a/a7/2-3_guajeo.mid/2-3_guajeo.mid.ogg" type="audio/ogg; codecs=&quot;vorbis&quot;" data-transcodekey="ogg" data-width="0" data-height="0">
<source src="https://upload.wikimedia.org/wikipedia/commons/a/a7/2-3_guajeo.mid" type="audio/midi" data-width="0" data-height="0">
</audio>

The original file can be download directly at the third link:
https://upload.wikimedia.org/wikipedia/commons/a/a7/2-3_guajeo.mid
'''
from __future__ import print_function
import os
import requests
import shutil
import sys

# from xml.etree.ElementTree import Element

import lxml.html as lh


if sys.version_info.major >= 3:
    from urllib.request import urlopen
    from urllib.parse import unquote
else:
    from urllib2 import urlopen  # noqa: F401 # type: ignore
    from urllib2 import unquote  # type: ignore

pseudo_colon = "ː"  # psuedo-colon, not real colon!
pseudo_protocol = "Fileː"

# <https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy>
# requires a proper user agent string:
UA = ("User-Agent: FileReFollow/0.2"
      " (https://github.com/Poikilos/filerefollow) filerefollow/0.2")

headers = {'User-Agent': UA}


def undo():
    for sub in os.listdir("."):
        if sub.lower().endswith(".mid") and not sub.startswith(pseudo_protocol):
            # UNDO
            # (in case the files are still HTML and not really MIDI data):
            new = pseudo_protocol + sub
            shutil.move(sub, new)
            continue


def text_tail(node):
    # See <https://stackoverflow.com/a/3569555/4541104>
    yield node.text
    yield node.tail


def download(url, file_name):
    """Download the given URL to a file.
    Note that WikiMedia Foundation requires a proper
      user agent string.
    - Requires the 'User-Agent' key of the `headers` global dict to be
      set to a valid user agent string (formatted like: "<client
      name>/<version> (<contact information>) <library/framework
      name>/<version> [<library name>/<version> ...]").
    """
    # See <https://stackoverflow.com/a/15645088/4541104>
    with open(file_name, "wb") as f:
        print("Downloading %s" % file_name)
        response = requests.get(url, stream=True, headers=headers)
        total_length = response.headers.get('content-length')
        if total_length is None:  # no content length header
            f.write(response.content)
        else:
            dl = 0
            total_length = int(total_length)
            for data in response.iter_content(chunk_size=4096):
                dl += len(data)
                f.write(data)
                done = int(50 * dl / total_length)
                sys.stdout.write("\r[%s%s]" % ('=' * done, ' ' * (50 - done)))
                sys.stdout.flush()


def is_html_file(dst):
    with open(dst, "rb") as f:
        opener = f.read(10)
        if opener.upper().startswith(b"<!DOCTYPE "):
            return True
        else:
            print("{} is not b\"<!DOCTYPE \"".format(opener))
    return False


def redownload(html_path, extensions=["mid"], folder=None,
               binary_path=None, html_folder=None):
    """Re-download binary file(s) using a file saved with a binary
    extension that is really a WikiMedia Commons page representing a
    binary file. See the submodule docstring for more info and an
    example.

    Args:
        html_path (str): An HTML file to read (containing "source"
            tag(s)).
        extensions (list[str], optional): What file extensions to save
            (case insensitive). Defaults to ["mid"].
        folder (str, optional): Where to save files. Ignored if
            binary_path is set & raises ValueError. Defaults to "media".
        binary_path (str, optional): Where to save the file (optional).
            Ignored if binary_path is set & raises ValueError. Defaults
            to the actual filename in the source tag's src attribute.
        html_folder (str, optional): Where to move html files with
            bad (binary) extensions. Defaults to "html". Warning: Do not
            make this the same as the folder, because otherwise if there
            is a failure then some files will be binary and some will
            still be HTML.

    Raises:
        ValueError: If both binary_path and folder are set.
    """
    # https://stackoverflow.com/a/3569555/4541104
    # url = 'http://bit.ly/bf1T12'
    # doc = lh.parse(urlopen(url))
    if binary_path is not None:
        if folder is not None:
            raise ValueError(
                "Destination folder cannot be set because binary_path is set"
            )
    else:
        if folder is None:
            folder = "media"
        if not os.path.isdir(folder):
            os.makedirs(folder)
    if html_folder is None:
        html_folder = "html"
        if not os.path.isdir(html_folder):
            os.makedirs(html_folder)
    doc = lh.parse(html_path)
    dot_exts = ["."+ext.lower() for ext in extensions]
    got = None
    _, old_name = os.path.split(html_path)
    found_url = False
    for elt in doc.iter():  # doc.iter('source') doesn't work
        # text = elt.text_content()
        # if not elt:
        #     elt = Element()
        #     elt.attrib
        #     elt.tag
        # items = elt.items()
        if 'src' not in elt.attrib:
            if elt.tag == "source:":
                print("  src is not in {}".format(elt))
            continue
        src = elt.attrib.get('src')
        found_url = src
        slash_i = src.rfind("/")
        encoded_name = src[slash_i+1:]
        name = unquote(encoded_name)
        _, dot_ext = os.path.splitext(src)
        if dot_ext.lower() not in dot_exts:
            # Skip the transcoded version (.mp3 *and* .ogg in the case of MIDI)
            continue
        encoded_dst = None
        if folder:
            encoded_dst = os.path.join(folder, encoded_name)
        if binary_path is None:
            dst = os.path.join(folder, name)
        else:
            dst = binary_path
            if got:
                print("Warning: skipping \"{}\""
                      " since binary_path was set (already got \"{}\")."
                      .format(binary_path, got))
                continue
        keep = os.path.isfile(dst)
        if keep:
            if is_html_file(dst):
                os.remove(dst)
                keep = False
        if keep:
            print("Skipping existing \"{}\"".format(dst))
        elif encoded_dst and os.path.isfile(encoded_dst):
            # Clean up from old versions of the script
            shutil.move(encoded_dst, dst)
            print("mv \"{}\" \"{}\"".format(encoded_dst, dst))
            got = encoded_dst
        else:
            print("# downloading \"{}\"".format(src))
            download(src, dst)
            if is_html_file(dst):
                print("Error: failed to download \"{}\""
                      .format(src))
                os.remove(dst)
                # Do *not* set got, or html file will get moved and not retried.
            else:
                print("# saved \"{}\"".format(dst))
                got = src
        # if text.startswith('Additional  Info'):
        #     blurb=[text for node in elt.itersiblings('td')
        #            for subnode in node.iter()
        #            for text in text_tail(subnode) if text and text!=u'\xa0']
        #     break
    if got:
        moved_old = os.path.join(html_folder, old_name)
        shutil.move(html_path, moved_old)
        print("mv \"{}\" \"{}\"".format(html_path, moved_old))
    if not found_url:
        print("Warning: There was no source with a \"src\" tag in {}"
              .format(html_path))


def redownload_all(parent):
    parent = os.path.realpath(parent)
    for sub in os.listdir(parent):
        if sub.startswith(pseudo_protocol):
            new = sub[5:]
            sub_path = os.path.join(parent, sub)
            # new_path = os.path.join(parent, new)
            # shutil.move(sub, new)
            # print("mv '{}' '{}'".format(sub, new))
            # ^ Don't do it! They are html not binary
            #   (if downloaded using DownloadThemAll)!
            redownload(sub_path)
            # binary_path=new_path
        elif sub.startswith("ː"):  # psuedo-colon, not real colon!
            new = sub[1:]
            shutil.move(sub, new)
            print("mv '{}' '{}'".format(sub, new))
        else:
            print("# skipping {}".format(sub))


def main_cli():
    redownload_all(".")
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
