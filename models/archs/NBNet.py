import paddle
import paddle.nn as nn


class ConvBlock(nn.Layer):
    def __init__(self, in_channel, out_channel, strides=1):
        super(ConvBlock, self).__init__()
        self.strides = strides
        self.block = nn.Sequential(
            nn.Conv2D(in_channel, out_channel, kernel_size=3, stride=strides, padding=1),
            nn.LeakyReLU(),
            nn.Conv2D(out_channel, out_channel, kernel_size=3, stride=strides, padding=1),
            nn.LeakyReLU(),
        )

        self.conv11 = nn.Conv2D(in_channel, out_channel, kernel_size=1, stride=strides, padding=0)

    def forward(self, x):
        out1 = self.block(x)
        out2 = self.conv11(x)
        out = out1 + out2
        return out


class SSA(nn.Layer):
    def __init__(self, in_channel, strides=1):
        super(SSA, self).__init__()

        self.conv1 = nn.Conv2D(in_channel, 16, kernel_size=3, stride=strides, padding=1)
        self.relu1 = nn.LeakyReLU()
        self.conv2 = nn.Conv2D(16, 16, kernel_size=3, stride=strides, padding=1)
        self.relu2 = nn.LeakyReLU()

        self.conv11 = nn.Conv2D(in_channel, 16, kernel_size=1, stride=strides, padding=0)

    def forward(self, input1, input2):
        input1 = input1.transpose([0, 2, 3, 1])
        input2 = input2.transpose([0, 2, 3, 1])
        cat = paddle.concat([input1, input2], 3)
        cat = cat.transpose([0, 3, 1, 2])
        out1 = self.relu1(self.conv1(cat))
        out1 = self.relu2(self.conv2(out1))
        out2 = self.conv11(cat)
        conv = (out1 + out2).transpose([0, 2, 3, 1])
        H, W, K, batch_size = conv.shape[1], conv.shape[2], conv.shape[3],conv.shape[0]
        # print(conv.shape)
        V = paddle.reshape(conv,[batch_size,H * W, K])
        # print("V  : ",V.shape)
        Vtrans = paddle.transpose(V, [0, 2, 1])
        # Vtrans = V.transpose(2, 1)
        # print("Vtrans  : ",Vtrans.shape)
        Vinverse = paddle.linalg.inv(paddle.bmm(Vtrans, V))
        Projection = paddle.bmm(paddle.bmm(V, Vinverse), Vtrans)
        # print("Projection  : ",Projection.shape)
        H1, W1, C1,batch_size = input1.shape[1], input1.shape[2], input1.shape[3], input1.shape[0]
        X1 = paddle.reshape(input1,[batch_size, H1 * W1, C1])
        # print("X1  : ",X1.shape)
        Yproj = paddle.bmm(Projection, X1)
        Y = paddle.reshape(Yproj,[batch_size, H1, W1, C1])
        Y = Y.transpose([0, 3, 1, 2])
        return Y


class NBNet(nn.Layer):
    def __init__(self, num_classes=10):
        super(NBNet, self).__init__()

        # device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        self.ConvBlock1 = ConvBlock(3, 32, strides=1)
        self.pool1 = nn.MaxPool2D(kernel_size=2)
        self.skip1 = nn.Sequential(ConvBlock(32, 32, strides=1), ConvBlock(32, 32, strides=1),
                                   ConvBlock(32, 32, strides=1), ConvBlock(32, 32, strides=1))
        self.ssa1 = SSA(64, strides=1)

        self.ConvBlock2 = ConvBlock(32, 64, strides=1)
        self.pool2 = nn.MaxPool2D(kernel_size=2)
        self.skip2 = nn.Sequential(ConvBlock(64, 64, strides=1), ConvBlock(64, 64, strides=1),
                                   ConvBlock(64, 64, strides=1))
        self.ssa2 = SSA(128, strides=1)

        self.ConvBlock3 = ConvBlock(64, 128, strides=1)
        self.pool3 = nn.MaxPool2D(kernel_size=2)
        self.skip3 = nn.Sequential(ConvBlock(128, 128, strides=1), ConvBlock(128, 128, strides=1))
        self.ssa3 = SSA(256, strides=1)

        self.ConvBlock4 = ConvBlock(128, 256, strides=1)
        self.pool4 = nn.MaxPool2D(kernel_size=2)
        self.skip4 = nn.Sequential(ConvBlock(256, 256, strides=1))
        self.ssa4 = SSA(512, strides=1)

        self.ConvBlock5 = ConvBlock(256, 512, strides=1)

        self.upv6 = nn.Conv2DTranspose(512, 256, 2, stride=2)
        self.ConvBlock6 = ConvBlock(512, 256, strides=1)

        self.upv7 = nn.Conv2DTranspose(256, 128, 2, stride=2)
        self.ConvBlock7 = ConvBlock(256, 128, strides=1)

        self.upv8 = nn.Conv2DTranspose(128, 64, 2, stride=2)
        self.ConvBlock8 = ConvBlock(128, 64, strides=1)

        self.upv9 = nn.Conv2DTranspose(64, 32, 2, stride=2)
        self.ConvBlock9 = ConvBlock(64, 32, strides=1)

        self.conv10 = nn.Conv2D(32, 3, kernel_size=3, stride=1, padding=1)

    def forward(self, x):
        conv1 = self.ConvBlock1(x)
        pool1 = self.pool1(conv1)

        conv2 = self.ConvBlock2(pool1)
        pool2 = self.pool2(conv2)

        conv3 = self.ConvBlock3(pool2)
        pool3 = self.pool3(conv3)

        conv4 = self.ConvBlock4(pool3)
        pool4 = self.pool4(conv4)

        conv5 = self.ConvBlock5(pool4)

        up6 = self.upv6(conv5)
        skip4 = self.skip4(conv4)
        skip4 = self.ssa4(skip4, up6)
        up6 = paddle.concat([up6, skip4], 1)
        conv6 = self.ConvBlock6(up6)

        up7 = self.upv7(conv6)
        skip3 = self.skip3(conv3)
        skip3 = self.ssa3(skip3, up7)
        up7 = paddle.concat([up7, skip3], 1)
        conv7 = self.ConvBlock7(up7)

        up8 = self.upv8(conv7)
        skip2 = self.skip2(conv2)
        skip2 = self.ssa2(skip2, up8)
        up8 = paddle.concat([up8, skip2], 1)
        conv8 = self.ConvBlock8(up8)

        up9 = self.upv9(conv8)
        skip1 = self.skip1(conv1)
        skip1 = self.ssa1(skip1, up9)
        up9 = paddle.concat([up9, skip1], 1)
        conv9 = self.ConvBlock9(up9)

        conv10 = self.conv10(conv9)
        out = x + conv10

        return out
