import os
import hashlib
import json
from time import time
from uuid import uuid4
from textwrap import dedent
import flask
from flask import Flask, jsonify, request, render_template
from urllib.parse  import urlparse
import requests
from argparse import ArgumentParser
from flask_table import Table,Col
import sys
from selenium import webdriver

########## Side Functions and Classes #############
class ItemTable(Table):
    name = Col('Name')
    description = Col('Value')

########## Main Blockchain Class ################
class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.address = []
        self.new_block(previous_hash='1', proof=100)

    def register_node(self, address):
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            #print(f'{last_block}')
            #print(f'{block}')
            #print('\n-----------\n')
            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof'], self.hash(last_block)):
                return False

            last_block = block
            current_index += 1

        return True


    def resolve_conflicts(self):
        neighbors = self.nodes
        new_chain = None
        max_length = len(self.chain)

        for node in neighbors:
            response = requests.get(f'http://{node}/chain')
            #print(response)
            #if response.text.__contains__('html'):
                # CONVERT HTML TO JSON
                # Set response equal to the jsoniifed values

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                #print(chain)
                if length > max_length and self.valid_chain(chain):
                    new_chain = chain
                    max_length = length

        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, previous_hash, proof):
        block = {
            'index': len(self.chain)+1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }
        self.current_transactions = []
        self.chain.append(block)
        return block


    def new_transaction(self, sender, recipient, amount):
        self.current_transactions.append({'sender': sender,
        'recipient': recipient,
        'amount': amount})

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha3_256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_block):
        last_proof = last_block['proof']
        last_hash = self.hash(last_block)
        proof = 0
        while self.valid_proof(last_proof,proof, last_hash) is False:
            proof +=1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        guess=f'{last_proof}{proof}{last_hash}'.encode()
        hashGuess = hashlib.sha3_256(guess).hexdigest()
        return hashGuess[0:4] == "0000"


app = Flask(__name__)

node_identifier = str(uuid4()).replace('-','')

blockchain = Blockchain()

@app.route('/')
def main():
    return render_template('home.html')

@app.route('/ip', methods = ['GET'])
def ip():
    return jsonify({'ip': request.remote_addr}), 200

@app.route('/mine', methods = ['GET'])
def mine():
    replaced = {}
    if (blockchain.nodes) != 0:
        replaced = consensus()
    last_block = blockchain.last_block
    proof = blockchain.proof_of_work(last_block)

    blockchain.new_transaction(
        sender="0",
        recipient = node_identifier,
        amount = 1
    )

    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(previous_hash, proof)

    response = {
        'message' : 'New block created.',
        'index' : block['index'],
        'transactions' : block['transactions'],
        'proof' : block['proof'],
        'previous_hash' : block['previous_hash']
    }

    return render_template('mine.html', response=response, replaced= replaced, TEMPLATES_AUTO_RELOAD = True)


@app.route('/transactions/new', methods = ['GET'])
def add_transaction():
    return render_template('add_transaction.html')

@app.route('/transactions/new', methods = ['POST'])
def new_transaction():
    values = dict()
    values['sender'] = request.form.get('sender')
    values['recipient'] = request.form.get('recipient')
    values['amount'] = request.form.get('amount')

    required = ['sender','recipient', 'amount']
    if not all(k in values for k in required):
        return "Missing transactional values. Please enter all values.", 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message' : f'Transaction will be added to Block {index}'}

    return render_template('transaction_successful.html', response = response, TEMPLATES_AUTO_RELOAD = True)

@app.route('/chain', methods = ['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }

    # return render_template('chain.html', response= (jsonify(response), 200), TEMPLATES_AUTO_RELOAD = True)
    return jsonify(response), 200



@app.route('/nodes/register', methods = ['GET'])
def get_node_information():
    return render_template('add_nodes.html')

@app.route('/nodes/register', methods = ['POST'])
def register_nodes():
    values = dict()
    values['nodes'] = request.form.get('nodes')
    #values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: please supply a valid list of nodes.", 400

    if type(nodes) is list:
        for node in nodes:
            blockchain.register_node(node)
    else:
        blockchain.register_node(nodes)

    response = {
        'message' : 'New nodes have been added.',
        'total_nodes' : list(blockchain.nodes),
    }
    return render_template('nodes_registered.html', response = response)

def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        response = {
            'message': 'Our chain was not the longest; hence, it was replaced with the consensus.',
            'new_chain' : blockchain.chain
        }
    else:
        response = {
        }
    return response

if __name__=='__main__':
    parser = ArgumentParser()
    parser.add_argument('-p','--port',default = 5000, type = int, help = 'port to listen on')
    args = parser.parse_args()
    port = args.port
    app.run(host='0.0.0.0', port = port)
