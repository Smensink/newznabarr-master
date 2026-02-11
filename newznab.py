import email.utils
import time
import xml.etree.ElementTree as ET

def searchresults_to_response(server, results):
    root = ET.Element("rss", version="2.0", attrib={
        "xmlns:atom": "http://www.w3.org/2005/Atom", 
        "xmlns:newznab": "http://www.newznab.com/DTD/2010/feeds/attributes/"
    })
    channel = ET.SubElement(root, "channel")
    
    ET.SubElement(channel, "title").text = "NewzNabArr"
    ET.SubElement(channel, "description").text = "Multiple newznab proxies for starr apps"
    ET.SubElement(channel, "link").text = server

    pub_date = email.utils.formatdate(time.time())
    ET.SubElement(channel, "pubDate").text = pub_date

    for result in results:
        prefix = result["prefix"]
        link2 = f"{server}api?download=nzb&prefix={prefix}&url={result['link']}&size={result['size']}&title={result['title']}"
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = result["title"]
        ET.SubElement(item, "description").text = result["description"]
        ET.SubElement(item, "guid").text = result["guid"]
        ET.SubElement(item, "comments").text = result["comments"]
        pub_ts = result.get("pub_ts")
        if pub_ts:
            item_pub_date = email.utils.formatdate(pub_ts)
        else:
            item_pub_date = email.utils.formatdate(time.time())
        ET.SubElement(item, "pubDate").text = item_pub_date
        ET.SubElement(item, "size").text = result["size"]
        ET.SubElement(item, "link").text = link2
        ET.SubElement(item, "category").text = result["category"]
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", link2)
        enclosure.set("length", result["size"])  # Replace with actual file size if available
        enclosure.set("type", "application/x-nzb")  # or "application/epub" based on book format
    
        attr_pairs = [
            ("category", result["category"]),
            ("files", result.get("files", "1")),
            ("grabs", result.get("grabs", "100")),
        ]
        extra_attrs = {
            "author": result.get("author"),
            "booktitle": result.get("book_title"),
            "bookseries": result.get("series"),
            "publisher": result.get("publisher"),
            "format": result.get("format"),
            "language": result.get("language"),
            "year": result.get("year"),
        }
        if result.get("age") is not None:
            extra_attrs["age"] = result["age"]

        for name, value in attr_pairs:
            attr = ET.SubElement(item, "newznab:attr")
            attr.set("name", name)
            attr.set("value", str(value))

        for name, value in extra_attrs.items():
            if value:
                attr = ET.SubElement(item, "newznab:attr")
                attr.set("name", name)
                attr.set("value", str(value))
    xml_str = ET.tostring(root, encoding="utf-8", method="xml")
    return xml_str
