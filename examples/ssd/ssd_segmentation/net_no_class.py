import sys
sys.path.insert(0, '../../../python')

import caffe
from caffe import layers as L
from caffe import params as P
from caffe.proto import caffe_pb2

from caffe.model_libs import *
from google.protobuf import text_format

import math
import os
import shutil
import stat
import subprocess
import sys

# Add extra layers on top of a "base" network (e.g. VGGNet or Inception).
def AddExtraLayers(net, use_batchnorm=True, lr_mult=1):
    use_relu = True

    # Add additional convolutional layers.
    # 19 x 19
    from_layer = net.keys()[-1]

    # TODO(weiliu89): Construct the name using the last layer to avoid duplication.
    # 10 x 10
    out_layer = "conv6_1"
    ConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 256, 1, 0, 1,
        lr_mult=lr_mult)

    from_layer = out_layer
    out_layer = "conv6_2"
    ConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 512, 3, 1, 2,
        lr_mult=lr_mult)

    # 5 x 5
    from_layer = out_layer
    out_layer = "conv7_1"
    ConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 128, 1, 0, 1,
      lr_mult=lr_mult)

    from_layer = out_layer
    out_layer = "conv7_2"
    ConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 256, 3, 1, 2,
      lr_mult=lr_mult)

    # 3 x 3
    from_layer = out_layer
    out_layer = "conv8_1"
    ConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 128, 1, 0, 1,
      lr_mult=lr_mult)

    from_layer = out_layer
    out_layer = "conv8_2"
    ConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 256, 3, 0, 1,
      lr_mult=lr_mult)

    # 1 x 1
    from_layer = out_layer
    out_layer = "conv9_1"
    ConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 128, 1, 0, 1,
      lr_mult=lr_mult)

    from_layer = out_layer
    out_layer = "conv9_2"
    ConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 256, 3, 0, 1,
      lr_mult=lr_mult)

    return net

def AddExtraTopDownLayers(net, use_batchnorm=True, lr_mult=1, crop_layers=['conv6_2', 'conv7_2', 'conv8_2', 'conv9_2'], is_cls=False,
                          is_crop_all=False, is_crop_cls=False):
    # mbox_source_layers = ['conv4_3', 'fc7', 'conv6_2', 'conv7_2', 'conv8_2', 'conv9_2']
    bbox = "cls_specific_bbox"

    use_relu = True
    # 1 x 1

    if is_cls:
        from_layer = net.keys()[-1]

        out_layer = "decls"
        DeConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 256, 1, 0, 1, lr_mult=lr_mult)

    # crop feature form bottom-up net
    from_layer = "conv9_2"

    if from_layer in crop_layers:
        out_layer = "conv9_2_crop"
        net[out_layer] = L.CropBBox(net[from_layer], net[bbox], is_crop_all=is_crop_all, is_crop_cls=is_crop_cls)
    else:
        out_layer = "conv9_2"

    if is_cls:
        # concatenate the cropped feature and the class-specific top-down signals
        from_layer = out_layer
        out_layer = "deconv9_2_concat"
        net[out_layer] = L.Concat(net[from_layer], net["decls"])

    from_layer = out_layer
    out_layer = "deconv9_2"
    DeConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 128, 3, 0, 1,
                lr_mult=lr_mult)

    from_layer = out_layer
    out_layer = "deconv9_1"
    DeConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 256, 1, 0, 1,
                lr_mult=lr_mult)

    # crop feature form bottom-up net
    from_layer = "conv8_2"

    if from_layer in crop_layers:
        out_layer = "conv8_2_crop"
        net[out_layer] = L.CropBBox(net[from_layer], net[bbox], is_crop_all=is_crop_all, is_crop_cls=is_crop_cls)
    else:
        out_layer = from_layer

    # concatenate the cropped feature and the class-specific top-down signals
    from_layer = out_layer
    out_layer = "deconv8_2_concat"
    net[out_layer] = L.Concat(net[from_layer], net["deconv9_1"])

    # 3 x 3
    from_layer = out_layer
    out_layer = "deconv8_2"
    DeConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 128, 3, 0, 1,
      lr_mult=lr_mult)

    from_layer = out_layer
    out_layer = "deconv8_1"
    DeConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 256, 1, 0, 1,
                lr_mult=lr_mult)

    # crop feature form bottom-up net
    from_layer = "conv7_2"
    if from_layer in crop_layers:
        out_layer = "conv7_2_crop"
        net[out_layer] = L.CropBBox(net[from_layer], net[bbox], is_crop_all=is_crop_all, is_crop_cls=is_crop_cls)
    else:
        out_layer = from_layer

    # concatenate the cropped feature and the class-specific top-down signals
    from_layer = out_layer
    out_layer = "deconv7_2_concat"
    net[out_layer] = L.Concat(net[from_layer], net["deconv8_1"])

    # 5 x 5
    from_layer = out_layer
    out_layer = "deconv7_2"
    DeConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 128, 3, 1, 2,
                lr_mult=lr_mult)

    from_layer = out_layer
    out_layer = "deconv7_1"
    DeConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 512, 1, 0, 1,
      lr_mult=lr_mult)

    # crop feature form bottom-up net
    from_layer = "conv6_2"
    if from_layer in crop_layers:
        out_layer = "conv6_2_crop"
        net[out_layer] = L.CropBBox(net[from_layer], net[bbox], is_crop_all=is_crop_all, is_crop_cls=is_crop_cls)
    else:
        out_layer = from_layer

    # concatenate the cropped feature and the class-specific top-down signals
    from_layer = out_layer
    out_layer = "deconv6_2_concat"
    net[out_layer] = L.Concat(net[from_layer], net["deconv7_1"])

    # 10 x 10
    from_layer = out_layer
    out_layer = "deconv6_2"
    DeConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 256, 3, 1, 2,
                lr_mult=lr_mult)

    from_layer = out_layer
    out_layer = "deconv6_1"
    DeConvBNLayer(net, from_layer, out_layer, use_batchnorm, use_relu, 1024, 1, 0, 1,
        lr_mult=lr_mult)

    return net


def vgg16_ssd_seg(source, bbox_seg_data_param, kwargs, use_batchnorm=False, lr_mult=1, crop_layers=[],
                  is_crop_last=False, is_cls=False, is_deploy=False, is_crop_all=False,
                  is_crop_cls=False, is_crop_merge_feature=False):

        if crop_layers is None:
            crop_layers = ['conv4_3', 'fc7', 'conv6_2', 'conv7_2', 'conv8_2', 'conv9_2']
        net = caffe.NetSpec()
        if is_deploy:
            net.data = L.Input(input_param=dict(shape=dict(dim=[1, 3, 320, 320])))
            net.cls_specific_bbox = L.Input(input_param=dict(shape=dict(dim=[1, 1, 1, 8])))
            if is_cls:
                net.cls = L.Input(input_param=dict(shape=dict(dim=[1, 20])))
        else:
            net.data, net.bbox, net.seg = L.BBoxSegData(name="data", annotated_data_param=bbox_seg_data_param,
                    data_param=dict(batch_size=8, backend=P.Data.LMDB, source=source),
                    ntop=3, **kwargs)

            net.cls_specific_bbox, net.binary_mask, net.cls = L.SelectBinary(net.bbox, net.seg, random_select=True, num_class=20, ntop=3)

        VGGNetBody(net, from_layer='data', fully_conv=True, reduced=True, dilated=True,
                   dropout=False, pool_mask=True, freeze_all=True)

        AddExtraLayers(net, use_batchnorm, lr_mult=0)

        if is_deploy:
            # MultiBoxLoss parameters.
            num_classes = 21
            share_location = True
            background_label_id = 0
            train_on_diff_gt = True
            normalization_mode = P.Loss.VALID
            code_type = P.PriorBox.CENTER_SIZE
            ignore_cross_boundary_bbox = False
            mining_type = P.MultiBoxLoss.MAX_NEGATIVE
            neg_pos_ratio = 3.
            loc_weight = (neg_pos_ratio + 1.) / 4.
            multibox_loss_param = {
                'loc_loss_type': P.MultiBoxLoss.SMOOTH_L1,
                'conf_loss_type': P.MultiBoxLoss.SOFTMAX,
                'loc_weight': loc_weight,
                'num_classes': num_classes,
                'share_location': share_location,
                'match_type': P.MultiBoxLoss.PER_PREDICTION,
                'overlap_threshold': 0.5,
                'use_prior_for_matching': True,
                'background_label_id': background_label_id,
                'use_difficult_gt': train_on_diff_gt,
                'mining_type': mining_type,
                'neg_pos_ratio': neg_pos_ratio,
                'neg_overlap': 0.5,
                'code_type': code_type,
                'ignore_cross_boundary_bbox': ignore_cross_boundary_bbox,
            }

            # parameters for generating priors.
            # minimum dimension of input image
            min_dim = 320
            # conv4_3 ==> 38 x 38
            # fc7 ==> 19 x 19
            # conv6_2 ==> 10 x 10
            # conv7_2 ==> 5 x 5
            # conv8_2 ==> 3 x 3
            # conv9_2 ==> 1 x 1
            mbox_source_layers = ['conv4_3', 'fc7', 'conv6_2', 'conv7_2', 'conv8_2', 'conv9_2']
            # in percent %
            min_ratio = 20
            max_ratio = 90
            step = int(math.floor((max_ratio - min_ratio) / (len(mbox_source_layers) - 2)))
            min_sizes = []
            max_sizes = []
            for ratio in xrange(min_ratio, max_ratio + 1, step):
                min_sizes.append(min_dim * ratio / 100.)
                max_sizes.append(min_dim * (ratio + step) / 100.)
            min_sizes = [min_dim * 10 / 100.] + min_sizes
            max_sizes = [min_dim * 20 / 100.] + max_sizes
            steps = [8, 16, 32, 64, 100, 320]
            aspect_ratios = [[2], [2, 3], [2, 3], [2, 3], [2], [2]]
            # L2 normalize conv4_3.
            normalizations = [20, -1, -1, -1, -1, -1]
            # variance used to encode/decode prior bboxes.
            if code_type == P.PriorBox.CENTER_SIZE:
                prior_variance = [0.1, 0.1, 0.2, 0.2]
            else:
                prior_variance = [0.1]
            flip = True
            clip = False

            # parameters for generating detection output.
            det_out_param = {
                'num_classes': num_classes,
                'share_location': share_location,
                'background_label_id': background_label_id,
                'nms_param': {'nms_threshold': 0.45, 'top_k': 400},
                'keep_top_k': 200,
                'confidence_threshold': 0.01,
                'code_type': code_type,
            }

            mbox_layers = CreateMultiBoxHead(net, data_layer='data', from_layers=mbox_source_layers,
                                             use_batchnorm=use_batchnorm, min_sizes=min_sizes, max_sizes=max_sizes,
                                             aspect_ratios=aspect_ratios, steps=steps, normalizations=normalizations,
                                             num_classes=num_classes, share_location=share_location, flip=flip,
                                             clip=clip,
                                             prior_variance=prior_variance, kernel_size=3, pad=1, lr_mult=lr_mult)

            conf_name = "mbox_conf"
            if multibox_loss_param["conf_loss_type"] == P.MultiBoxLoss.SOFTMAX:
                reshape_name = "{}_reshape".format(conf_name)
                net[reshape_name] = L.Reshape(net[conf_name], shape=dict(dim=[0, -1, num_classes]))
                softmax_name = "{}_softmax".format(conf_name)
                net[softmax_name] = L.Softmax(net[reshape_name], axis=2)
                flatten_name = "{}_flatten".format(conf_name)
                net[flatten_name] = L.Flatten(net[softmax_name], axis=1)
                mbox_layers[1] = net[flatten_name]
            elif multibox_loss_param["conf_loss_type"] == P.MultiBoxLoss.LOGISTIC:
                sigmoid_name = "{}_sigmoid".format(conf_name)
                net[sigmoid_name] = L.Sigmoid(net[conf_name])
                mbox_layers[1] = net[sigmoid_name]

            net.detection_out = L.DetectionOutput(*mbox_layers,
                                                  detection_output_param=det_out_param,
                                                  include=dict(phase=caffe_pb2.Phase.Value('TEST')))

        if not is_cls:
            if not is_deploy:
                net.__setattr__('cls_silence', L.Silence(net.cls, ntop=0))
        else:
            # class vector embedding deconvolution net for class-specific semantic segmentation
            net.cls_reshape = L.Reshape(net.cls, shape=dict(dim=[0, 0, 1, 1]))

        # add top-down deconvolution net
        # mbox_source_layers = ['conv4_3', 'fc7', 'conv6_2', 'conv7_2', 'conv8_2', 'conv9_2']
        AddExtraTopDownLayers(net, use_batchnorm=True, lr_mult=1, crop_layers=crop_layers, is_cls=is_cls, is_crop_all=is_crop_all, is_crop_cls=is_crop_cls)

        DeVGGNetBody(net, from_layer='deconv6_1', fully_conv=True, reduced=True, dilated=True,
                     dropout=False, pool_mask=True, extra_crop_layers=crop_layers, is_crop_all=is_crop_all,
                     is_crop_cls=is_crop_cls, is_crop_merge_feature=is_crop_merge_feature)

        dekwargs = {
            'weight_filler': dict(type='xavier'),
            'bias_filler': dict(type='constant', value=0)}
        deparam = {'param': [dict(lr_mult=1, decay_mult=1), dict(lr_mult=2, decay_mult=0)]}
        net.seg_score = L.Deconvolution(net.derelu1_1, convolution_param=dict(num_output=2, pad=1, kernel_size=3, **dekwargs), **deparam)

        if is_crop_last:
            out_layer = "seg_score_crop"
            net[out_layer] = L.CropBBox(net["seg_score"], net["cls_specific_bbox"], is_crop_score_map=True)
        else:
            out_layer = "seg_score"

        if is_deploy:
            net.seg_prob = L.Softmax(net[out_layer])
        else:
            net.seg_loss = L.SoftmaxWithLoss(net[out_layer], net.binary_mask, loss_param=dict(ignore_label=255))

        return net.to_proto()

if __name__ == "__main__":
        resize_width = 320
        resize_height = 320
        resize = "{}x{}".format(resize_width, resize_height)
        batch_sampler = [
                {
                        'sampler': {
                        },
                        'max_trials': 1,
                        'max_sample': 1,
                },
                {
                        'sampler': {
                                'min_scale': 0.3,
                                'max_scale': 1.0,
                                'min_aspect_ratio': 0.5,
                                'max_aspect_ratio': 2.0,
                        },
                        'sample_constraint': {
                                'min_jaccard_overlap': 0.1,
                        },
                        'max_trials': 50,
                        'max_sample': 1,
                },
                {
                        'sampler': {
                                'min_scale': 0.3,
                                'max_scale': 1.0,
                                'min_aspect_ratio': 0.5,
                                'max_aspect_ratio': 2.0,
                        },
                        'sample_constraint': {
                                'min_jaccard_overlap': 0.3,
                        },
                        'max_trials': 50,
                        'max_sample': 1,
                },
                {
                        'sampler': {
                                'min_scale': 0.3,
                                'max_scale': 1.0,
                                'min_aspect_ratio': 0.5,
                                'max_aspect_ratio': 2.0,
                        },
                        'sample_constraint': {
                                'min_jaccard_overlap': 0.5,
                        },
                        'max_trials': 50,
                        'max_sample': 1,
                },
                {
                        'sampler': {
                                'min_scale': 0.3,
                                'max_scale': 1.0,
                                'min_aspect_ratio': 0.5,
                                'max_aspect_ratio': 2.0,
                        },
                        'sample_constraint': {
                                'min_jaccard_overlap': 0.7,
                        },
                        'max_trials': 50,
                        'max_sample': 1,
                },
                {
                        'sampler': {
                                'min_scale': 0.3,
                                'max_scale': 1.0,
                                'min_aspect_ratio': 0.5,
                                'max_aspect_ratio': 2.0,
                        },
                        'sample_constraint': {
                                'min_jaccard_overlap': 0.9,
                        },
                        'max_trials': 50,
                        'max_sample': 1,
                },
                {
                        'sampler': {
                                'min_scale': 0.3,
                                'max_scale': 1.0,
                                'min_aspect_ratio': 0.5,
                                'max_aspect_ratio': 2.0,
                        },
                        'sample_constraint': {
                                'max_jaccard_overlap': 1.0,
                        },
                        'max_trials': 50,
                        'max_sample': 1,
                },
        ]
        transform_param = {
                'mirror': True,
                'mean_value': [104, 117, 123],
                'resize_param': {
                        'prob': 1,
                        'resize_mode': P.Resize.WARP,
                        'height': resize_height,
                        'width': resize_width,
                        'interp_mode': [
                                P.Resize.LINEAR,
                                P.Resize.AREA,
                                P.Resize.NEAREST,
                                P.Resize.CUBIC,
                                P.Resize.LANCZOS4,
                        ],
                },
                'distort_param': {
                        'brightness_prob': 0.5,
                        'brightness_delta': 32,
                        'contrast_prob': 0.5,
                        'contrast_lower': 0.5,
                        'contrast_upper': 1.5,
                        'hue_prob': 0.5,
                        'hue_delta': 18,
                        'saturation_prob': 0.5,
                        'saturation_lower': 0.5,
                        'saturation_upper': 1.5,
                        'random_order_prob': 0.0,
                },
                'expand_param': {
                        'prob': 0.5,
                        'max_expand_ratio': 4.0,
                },
                'emit_constraint': {
                        'emit_type': caffe_pb2.EmitConstraint.CENTER,
                }
        }

        kwargs = {'include': dict(phase=caffe_pb2.Phase.Value('TRAIN')),
                  'transform_param': transform_param}

        label_map_file = "data/VOC0712/labelmap_voc.prototxt"
        bbox_seg_data_param = {
                'label_map_file': label_map_file,
                'batch_sampler': batch_sampler,
        }
        source = "/home/amax/NiuChuang/data/VOCdevkit/VOC0712/lmdb/VOC0712_trainval_lmdb_test2"
        # crop_layers = ["conv4_3", "fc7", "conv6_2", "conv7_2", "conv8_2",  "conv9_2"]
        crop_layers = []
        is_deploy = False
        is_crop_all = False
        is_crop_cls = False
        is_crop_last = False
        is_cls = False
        is_crop_merge_feature = True
        save_file = "vgg16_ssd_seg_noclass_crop_merge_feature.prototxt"  # "vgg16_ssd_seg_crop_last.prototxt"
        with open(save_file, 'w') as f:
            f.write(str(vgg16_ssd_seg(source, bbox_seg_data_param, kwargs, crop_layers=crop_layers,
                                      is_crop_last=is_crop_last, is_cls=is_cls, is_deploy=is_deploy,
                                      is_crop_all=is_crop_all, is_crop_cls=is_crop_cls,
                                      is_crop_merge_feature=is_crop_merge_feature)))