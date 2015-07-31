# APKfetch
Library for downloading APK files from the Google Play store.


### Dependencies
* Python 2.7+
* requests
* protobuf

The requests/protobuf packages can be installed with

    pip install requests
    pip install protobuf


### Example

Using the library is as simple as:

```python
from APKfetch.apkfetch import APKfetch

def main():
  apk = APKfetch()
  apk.login('you@gmail.com', 'yourpassword')
  apk.fetch('com.somepackage')

if __name__ == '__main__':
    main()
```

 Note that the example creates a new android id. If you wish to use an existing id, you should login using:
 
 ```python
 apk.login('you@gmail.com', 'yourpassword', 'yourandroidid')
 ```