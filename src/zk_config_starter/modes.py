"""Storage mode enum for zk-config-starter."""
import enum


class StorageMode(enum.Enum):
    """How properties are stored in the watched Zookeeper path.

    Attributes:
        CHILDREN_AS_KEYS: Each child znode represents one property.
            The znode name is the key; the znode's data bytes are the value.
            Example layout::

                /config
                  ├── db.host  (data: "localhost")
                  ├── db.port  (data: "5432")
                  └── app.env  (data: "production")

        PROPERTIES_FILE: The watched znode itself holds a ``key=value`` text
            blob (one property per line), similar to a Java ``.properties``
            file.  The SDK parses the blob and populates the store from it.
            Example layout::

                /config  (data: "db.host=localhost\\ndb.port=5432\\n")
    """

    CHILDREN_AS_KEYS = "children"
    PROPERTIES_FILE = "properties"
