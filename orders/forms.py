from django import forms


class OrderCreateForm(forms.Form):
    """下单表单：只暴露留言，买家/商品/价格均由服务端推导，杜绝改价与代下单。"""

    message = forms.CharField(
        label='留言（选填）',
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': '可给卖家留言，最多 500 字（可留空）',
        }),
        error_messages={
            'max_length': '留言不能超过 500 个字符',
        },
    )


class ReviewForm(forms.Form):
    """评价表单：只暴露评价正文；订单、评价人与被评人均由服务端从登录用户与订单推导。"""

    content = forms.CharField(
        label='评价内容',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': '请输入对本次交易的真实评价',
        }),
        error_messages={
            'required': '评价内容不能为空',
        },
    )
