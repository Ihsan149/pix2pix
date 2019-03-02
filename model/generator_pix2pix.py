import numpy as np
import os
import skimage.io as io
import skimage.transform as trans
from tensorflow.keras.models import *
from tensorflow.keras.layers import *
from tensorflow.keras.optimizers import *
from tensorflow.keras.callbacks import ModelCheckpoint, LearningRateScheduler


def downconv(x, out_channels, activation=True, batch_norm=True):
    
    conv_kwargs = dict(
        padding='same', 
        kernel_initializer='he_normal',              
        data_format='channels_last'
    )
    
    bn_kwargs = dict(
        axis=-1,         # because data_loader returns channels last
        momentum=0.9,    # equivalent to pytorch defaults used by author (0.1 in pytorch -> 0.9 in keras/tf)
        epsilon=1e-5,    # match pytorch defaults
        trainable=True   # referred to as "Instance Normalization" by authors
    )
    
    if activation: x = LeakyReLU(alpha=0.2)(x)
    x = Conv2D(out_channels, 4, strides=2, **conv_kwargs)(x)
    if batch_norm: x = BatchNormalization(**bn_kwargs)(x)
    return x


def upconv(x, out_channels, batch_norm=True, dropout=False):
    conv_kwargs = dict(
        padding='same', 
        kernel_initializer='he_normal',              
        data_format='channels_last'
    )
    
    bn_kwargs = dict(
        axis=-1,         # because data_loader returns channels last
        momentum=0.9,    # equivalent to pytorch defaults used by author (0.1 in pytorch -> 0.9 in keras/tf)
        epsilon=1e-5,    # match pytorch defaults
        trainable=True   # referred to as "Instance Normalization" by authors
    )
    
    # Concatenate shortcut and input by channel axis
    if isinstance(x, list):
        x = concatenate(x, axis=-1)
    
    # Transpose convolution
    activation: x = ReLU()(x)
    x = Conv2DTranspose(out_channels, 4, strides=2, **conv_kwargs)(x)
    if batch_norm: x = BatchNormalization(**bn_kwargs)(x)
    if dropout:    x = Dropout(0.5)(x)
    return x
    

# INTENDED API
# ------------------------------------------------------------------------------

def unet_pix2pix(input_size=(256,256,1), output_channels=1):
    """
    A Keras/Tensorflow implementation of the U-net used in the latest pix2pix 
    PyTorch official implementation:
    https://github.com/junyanz/pytorch-CycleGAN-and-pix2pix
    
    This architecture is used as the Generator in the pix2pix GAN. It is similar
    to the original U-Net architecture with some notable modifications:
    - addition of batch normalisation after each convolution
    - Use of LeakyReLU instead of ReLU for encoder layer activations
    - convolutional stride 2, and kernels size 4 used everywhere as instead of
      2/1 stride and kernel size 3 in original
      
    Known discrepencies:
    - Authors' pytorch repo implies batchnorm is not trainable, 
      but here we use trainable batch norm layers. Results are
      poor otherwise.
    
    """
    
    oc = output_channels

    
    # ----------------------------------------------------------------
    # U-net
    
    # outermost
    inputs = Input(input_size)                                     # (256, 256, input_size[-1])
    e1 = downconv(inputs, 64, activation=False, batch_norm=False)  # (128, 128, 64)
    e2 = downconv(e1, 128, activation=True, batch_norm=True)       # (64, 64, 128)
    e3 = downconv(e2, 256, activation=True, batch_norm=True)       # (32, 32, 256)
    e4 = downconv(e3, 512, activation=True, batch_norm=True)       # (16, 16, 512)
    e5 = downconv(e4, 512, activation=True, batch_norm=True)       # (8, 8, 512)
    e6 = downconv(e5, 512, activation=True, batch_norm=True)       # (4, 4, 512)
    e7 = downconv(e6, 512, activation=True, batch_norm=True)       # (2, 2, 512)
    
    # innermost
    e8 = downconv(e7, 512, activation=True, batch_norm=False)      # (1 x 1 x 512)
    d8 = upconv(e8, 512, batch_norm=True, dropout=False)           # (2 x 2 x 512)

    d7 = upconv([d8, e7], 512, batch_norm=True, dropout=True)      # (4, 4, 512)
    d6 = upconv([d7, e6], 512, batch_norm=True, dropout=True)      # (8, 8, 512)
    d5 = upconv([d6, e5], 512, batch_norm=True, dropout=True)      # (16, 16, 512)
    d4 = upconv([d5, e4], 256, batch_norm=True, dropout=False)     # (32, 32, 256)
    d3 = upconv([d4, e3], 128, batch_norm=True, dropout=False)     # (64, 64, 128)
    d2 = upconv([d3, e2],  64, batch_norm=True, dropout=False)     # (128, 128, 64)
    d1 = upconv([d2, e1], oc, batch_norm=False, dropout=False)     # (256, 256, output_channels)
    op = Activation('tanh')(d1)

    model = Model(inputs=[inputs], outputs=[op], name='unet_pix2pix')
    print(model.summary())
    return model