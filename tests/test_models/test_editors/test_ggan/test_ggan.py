# Copyright (c) OpenMMLab. All rights reserved.
from copy import deepcopy
from unittest import TestCase

import torch
from mmengine import MessageHub
from mmengine.optim import OptimWrapper, OptimWrapperDict
from torch.optim import SGD

from mmedit.models import GGAN, GenDataPreprocessor
from mmedit.registry import MODELS

generator = dict(
    type='DCGANGenerator', noise_size=10, output_scale=16, base_channels=16)
discriminator = dict(
    type='DCGANDiscriminator', input_scale=16, output_scale=4, out_channels=1)


class TestGGAN(TestCase):

    def test_init(self):
        gan = GGAN(
            noise_size=10,
            data_preprocessor=GenDataPreprocessor(),
            generator=generator,
            discriminator=discriminator)

        self.assertIsInstance(gan, GGAN)
        self.assertIsInstance(gan.data_preprocessor, GenDataPreprocessor)

        # test only generator have noise size
        gen_cfg = deepcopy(generator)
        gen_cfg['noise_size'] = 10
        gan = GGAN(
            generator=gen_cfg,
            discriminator=discriminator,
            data_preprocessor=GenDataPreprocessor())
        self.assertEqual(gan.noise_size, 10)

        # test init with nn.Module
        gen_cfg = deepcopy(generator)
        gen_cfg['noise_size'] = 10
        disc_cfg = deepcopy(discriminator)
        gen = MODELS.build(gen_cfg)
        disc = MODELS.build(disc_cfg)
        gan = GGAN(
            generator=gen,
            discriminator=disc,
            data_preprocessor=GenDataPreprocessor())
        self.assertEqual(gan.generator, gen)
        self.assertEqual(gan.discriminator, disc)

        # test init without discriminator
        gan = GGAN(generator=gen, data_preprocessor=GenDataPreprocessor())
        self.assertEqual(gan.discriminator, None)

    def test_train_step(self):
        # prepare model
        accu_iter = 1
        n_disc = 1
        message_hub = MessageHub.get_instance('test-ggan')
        gan = GGAN(
            noise_size=10,
            generator=generator,
            discriminator=discriminator,
            data_preprocessor=GenDataPreprocessor(),
            discriminator_steps=n_disc)
        # prepare messageHub
        message_hub.update_info('iter', 0)
        # prepare optimizer
        gen_optim = SGD(gan.generator.parameters(), lr=0.1)
        disc_optim = SGD(gan.discriminator.parameters(), lr=0.1)
        optim_wrapper_dict = OptimWrapperDict(
            generator=OptimWrapper(gen_optim, accumulative_counts=accu_iter),
            discriminator=OptimWrapper(
                disc_optim, accumulative_counts=accu_iter))
        # prepare inputs
        img = torch.randn(1, 3, 16, 16)
        data = dict(inputs=dict(img=img))

        # simulate train_loop here
        for idx in range(n_disc * accu_iter):
            message_hub.update_info('iter', idx)
            log = gan.train_step(data, optim_wrapper_dict)
            if (idx + 1) == n_disc * accu_iter:
                # should update at after (n_disc * accu_iter)
                self.assertEqual(
                    set(log.keys()),
                    set([
                        'loss', 'loss_disc_fake', 'loss_disc_real', 'loss_gen'
                    ]))
            else:
                # should not update when discriminator's updating is unfinished
                self.assertEqual(
                    log.keys(),
                    set(['loss', 'loss', 'loss_disc_fake', 'loss_disc_real']))
