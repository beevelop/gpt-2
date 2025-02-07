#!/usr/bin/env python3

import json
import os

import fire
import numpy as np
import tensorflow as tf
from flask import Flask, render_template, request

import encoder
import model
import sample


app = Flask(__name__)

def init_model(
    model_name='1558M',
    nsamples=1,
    batch_size=1,
    length=None,
    temperature=1,
    top_k=0,
    top_p=1,
    models_dir='models',
):
    models_dir = os.path.expanduser(os.path.expandvars(models_dir))
    if batch_size is None:
        batch_size = 1
    assert nsamples % batch_size == 0

    enc = encoder.get_encoder(model_name, models_dir)
    hparams = model.default_hparams()
    with open(os.path.join('models', model_name, 'hparams.json')) as f:
        hparams.override_from_dict(json.load(f))

    if length is None:
        length = hparams.n_ctx // 2
    elif length > hparams.n_ctx:
        raise ValueError("Can't get samples longer than window size: %s" % hparams.n_ctx)

    graph = tf.Graph()
    sess = tf.Session(graph=graph)

    with sess.as_default(), graph.as_default():
        context = tf.placeholder(tf.int32, [batch_size, None])
        output = sample.sample_sequence(
            hparams=hparams, length=length,
            context=context,
            batch_size=batch_size,
            temperature=temperature, top_k=top_k, top_p=top_p
        )

        saver = tf.train.Saver()
        ckpt = tf.train.latest_checkpoint(os.path.join('models', model_name))
        saver.restore(sess, ckpt)

    return (enc, sess, output, context)


GENERATOR_MODEL = None
CACHE_MODEL = False  # set to True to keep the model loaded

@app.route('/', methods=('GET', 'POST'))
def hello():
    prompt = ""
    texts = []
    samples = 3
    if request.method == 'POST':
        prompt = request.form['prompt'].strip()
        try:
            samples = int(request.form['samples'])
        except ValueError:
            pass

        if CACHE_MODEL:
            global GENERATOR_MODEL
            if GENERATOR_MODEL is None:
                GENERATOR_MODEL = init_model()
            (enc, sess, output, context) = GENERATOR_MODEL
        else:
            (enc, sess, output, context) = init_model()

        if prompt:
            context_tokens = enc.encode(prompt)
        else:
            context_tokens = [enc.encoder['<|endoftext|>']]
        for i in range(samples):
            out = sess.run(output, feed_dict={context: [context_tokens]})
            texts.append(enc.decode(out[0]))

        if not CACHE_MODEL:
            sess.close()

    return render_template("page.html", prompt=prompt, texts=texts, samples=samples)
