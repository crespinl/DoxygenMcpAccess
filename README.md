# DoxygenMcpAccess

MCP server to expose Doxygen documentation (XML output) to an AI agent.

Usage :

1. In the Doxyfile of your library, enable XML output:
    ```
    GENERATE_XML = YES
    ```
   then run `doxygen` normally. Doxygen produces a `xml/` directory
   (by default) containing an `index.xml` + one XML file per documented
   entity (class, file, namespace...).

2. Install the dependencies:
    ```
    pip install -r requirements.txt
    ```

3. Run the server, pointing to the `xml/` directory and giving it a name
   that includes the library name (used in tool names to avoid confusion
   with the current project) :
    ```
    DOXYGEN_XML_DIR=/path/to/xml \
    LIBRARY_NAME=libfoo \
    python doxygen_mcp_server.py
    ```

4. The MCP server is now running at adress <http://127.0.0.1:9000/mcp>

## Tools 

The library name, LIBRARY_NAME, is injected into tool names to avoid
any ambiguity with the current project or the documentation from an other library :
- `search_symbols_in_<LIBRARY_NAME>(query)`
- `get_doc_from_<LIBRARY_NAME>(name)`
- `list_members_in_<LIBRARY_NAME>(class_name)`
