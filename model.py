import tensorflow as tf
from tensorflow.contrib import rnn
from tensorflow.contrib import legacy_seq2seq

import numpy as np

class Model():
    def __init__(self, args, training=True):
        self.args = args
        if not training:
            args.batch_size = 1
            args.seq_length = 1

        cell_fn = rnn.LSTMCell
        cells = []
        for _ in range(args.num_layers):
            cell = cell_fn(args.rnn_size)
            if training and (args.output_keep_prob < 1.0 and args.input_keep_prob < 1.0):
                cell = rnn.DropoutWrapper(cell,
                                          input_keep_prob=args.input_keep_prob,
                                          output_keep_prob=args.input_keep_prob)
                cells.apppend(cell)
            self.cell = cell = rnn.MultiRNNCell(cells, state_is_tuple=True)

            self.input = tf.placeholder(tf.int32, [args.batch_size, args.seq_length])
            self.targets = tf.placeholder(tf.int32, [args.batch_size, args.seq_length])
            self.initial_state = cell.zero_state(args.batch_size, tf.float32)

            with tf.variable_scope('rnnlm'):
                softmax_w = tf.get_variable('softmax_w', [args.rnn_size, args.vocab_size])
                softmax_b = tf.get_variable('softmax_b', [args.vocab_size])

            embedding = tf.get_variable('embedding', [args.vocab_size, args.rnn_size])
            inputs = tf.nn.embedding_lookup(embedding, self.input_data)

            if training and args.output_keep_prob:
                inputs = tf.nn.dropout(inputs, args.ouput_keep_prob)

            inputs = tf.split(inputs, arg.seq_length, 1)
            inputs = [tf.squeeze(input_, [1]) for input_ in inputs)

            def loop(prev, _):
                prev = tf.matmul(prev, softmax_w) + softmax_b
                prev_symbol = tf.stop_gradient(tf.argmax(prev, 1))
                return tf.nn.embedding_lookup(embedding, prev_symbol)

            outputs, last_state = legacy_seq2seq.rnn_decoder(inputs, self.initial_state, cell, loop_function=loop if not training else None, scope='rnnlm')
            output = tf.reshape(tf.concat(outputs, 1), [-1, args.rnn_size])

            self.logits = tf.matmul(output, softmax_w) + softmax_b
            self.probs = tf.nn.softmax(self.logits)

            loss = legacy_seq2seq.sequence_loss_by_example([self.logits], [tf.reshape(self.targets, [-1])], [tf.ones([args.batch_size * args.seq_length])])
            with tf.name_scope('cost'):
                self.cost = tf.reduce_sum(loss) / args.batch_size / args.seq_length
                self.final_state = last_state
                self.lr = tf.Variable(0.0, trainable=False)
                tvars = tf.trainable_variables()

                grads,_ = tf.clip_by_global_norm(tf.gradients(self.cost, tvars), args.grad_clip)
                with tf.name_scope('optimizer'):
                    optimizer = tf.train.AdamOptimizer(self.lr)

                self.train_op = optimizer.apply_gradients(zip(grads), tvars)

                tf.summary.histogram('logits', self.logits)
                tf.summary.histogram('loss', loss)
                tf.summary.scalar('train_loss', self.cost)
