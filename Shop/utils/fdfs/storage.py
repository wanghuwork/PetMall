from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client


class MyStorage(Storage):
    """fast dfs　文件存储类"""
    def __init__(self, client_conf=None, base_url=None):
        if client_conf == None:
            self.client_conf = './utils/fdfs/client.conf'
        self.client_conf = client_conf

        if base_url == None:
            self.base_url = 'http://176.234.11.18:8888/'
        self.base_url = base_url

    def _open(self, name, mode='rb'):
        pass

    def _save(self, name, content):
        '''保存文件时使用'''
        # name 选择上串文件的名字
        # ｃｏｎｔｅｎｔ　包含您上传文件内容的ｆｉｌｅ对象
        # 创建Fdfs_client对象
        client = Fdfs_client(self.client_conf)
        # 上传文件到ｆａｓｔ　ｄｆｓ　系统中
        res = client.upload_by_buffer(content.read())
        if res.get('Status') != 'Upload successed.':
            raise Exception('上传文件失败')
        # 获取返回的文件ＩＤ
        filename = res.get('Remote file_id')
        return filename

    def exists(self, name):
        '''Django判断文件名是否可用'''
        # 返回Ｆａｌｓｅ代表文件名都可用
        return False

    def url(self, name):
        '''Django返回访问文件的ＵＲｌ路径'''
        return self.base_url + name