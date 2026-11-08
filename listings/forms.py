from django import forms
from PIL import Image

from .models import Product

# 图片约束：每商品 1–5 张，单图 ≤5MB，仅 JPEG/PNG
MIN_IMAGES = 1
MAX_IMAGES = 5
MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG'}


def validate_images(files):
    """校验上传图片列表，返回中文错误列表；空列表表示全部通过。

    不信任扩展名：用 Pillow 打开并 verify()，按 img.format 判定真实格式。
    校验前后复位文件指针，保证后续保存的内容完整。
    """
    errors = []
    if len(files) < MIN_IMAGES:
        errors.append('请至少上传 1 张商品图片')
        return errors
    if len(files) > MAX_IMAGES:
        errors.append('最多只能上传 5 张商品图片')
        return errors

    for image_file in files:
        if image_file.size > MAX_IMAGE_SIZE:
            errors.append('单张图片不能超过 5MB')
            return errors
        try:
            image_file.seek(0)
            img = Image.open(image_file)
            image_format = img.format
            img.verify()
        except Exception:
            errors.append('图片文件损坏或格式不支持，仅支持 JPEG/PNG')
            image_file.seek(0)
            return errors
        image_file.seek(0)
        if image_format not in ALLOWED_IMAGE_FORMATS:
            errors.append('仅支持 JPEG/PNG 格式的图片')
            return errors
    return errors


class ProductForm(forms.ModelForm):
    """商品发布表单：仅承载五个可填字段，owner/status 由视图强制写入。"""

    class Meta:
        model = Product
        fields = ['title', 'description', 'price', 'condition', 'category']
        labels = {
            'title': '商品标题',
            'description': '商品描述',
            'price': '价格（元）',
            'condition': '成色',
            'category': '分类',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '请填写商品标题',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4, 'placeholder': '请描述商品状况',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0.01',
                'placeholder': '例如 25.00',
            }),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }
        error_messages = {
            'title': {
                'required': '请输入商品标题',
                'max_length': '商品标题不能超过 100 个字符',
            },
            'description': {
                'required': '请输入商品描述',
            },
            'price': {
                'required': '请输入价格',
                'invalid': '请输入有效的价格数字',
                'max_digits': '价格数字位数过长',
                'max_decimal_places': '价格最多保留 2 位小数',
                'max_whole_digits': '价格整数部分过长',
            },
            'condition': {
                'required': '请选择成色',
                'invalid_choice': '请选择有效的成色',
            },
            'category': {
                'required': '请选择分类',
                'invalid_choice': '请选择有效的分类',
            },
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price <= 0:
            raise forms.ValidationError('价格必须大于 0')
        return price
