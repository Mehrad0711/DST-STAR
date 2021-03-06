import torch
import numpy as np
import json
import time
import os
from copy import deepcopy


def model_evaluation(model, test_data, tokenizer, slot_meta, label_list, epoch, is_gt_p_state=False, pred_set_name='test'):
    model.eval()
    
    loss = 0.
    joint_acc = 0.
    joint_turn_acc = 0.
    slot_acc = np.array([0.] * len(slot_meta))
    
    results = {}
    last_dialogue_state = {}
    wall_times = [] 
    for di, i in enumerate(test_data):
        if i.turn_id == 0 or is_gt_p_state:
            last_dialogue_state = deepcopy(i.gold_last_state)
            
        i.last_dialogue_state = deepcopy(last_dialogue_state)
        i.make_instance(tokenizer)

        input_ids = torch.LongTensor([i.input_id]).to(model.device)
        input_mask = torch.LongTensor([i.input_mask]).to(model.device)
        segment_ids = torch.LongTensor([i.segment_id]).to(model.device)
        label_ids = torch.LongTensor([i.label_ids]).to(model.device)
        
        start = time.perf_counter()
        with torch.no_grad():
            t_loss, _, t_acc, t_acc_slot, t_pred_slot = model(input_ids=input_ids, attention_mask=input_mask,
                                                              token_type_ids=segment_ids, labels=label_ids,
                                                              eval_type="test")
            loss += t_loss.item()
            joint_acc += t_acc
            slot_acc += t_acc_slot
            
        end = time.perf_counter()
        wall_times.append(end - start)
        
        ss = {}
        ss["utter"] = i.turn_utter
        t_turn_label = []
        for s, slot in enumerate(slot_meta):
            v = label_list[s][t_pred_slot[0, s].item()]
            if v != last_dialogue_state[slot]:
                t_turn_label.append(slot + "-" + v)
            last_dialogue_state[slot] = v
            vv = label_list[s][i.label_ids[s]]
            ss[slot] = {}
            ss[slot]["pred"] = v
            ss[slot]["gt"] = vv
        
        if set(t_turn_label) == set(i.turn_label):
            joint_turn_acc += 1

        key = str(i.dialogue_id) + '_' + str(i.turn_id)
        results[key] = ss
        
    loss = loss / len(test_data)
    joint_acc_score = joint_acc / len(test_data)
    joint_turn_acc_score = joint_turn_acc / len(test_data)
    slot_acc_score = slot_acc / len(test_data)
       
    latency = np.mean(wall_times) * 1000 # ms
    
    print("------------------------------")
    print('is_gt_p_state: %s' % (str(is_gt_p_state)))
    print("Epoch %d loss : " % epoch, loss)
    print("Epoch %d joint accuracy : " % epoch, joint_acc_score)
    print("Epoch %d joint turn accuracy : " % epoch, joint_turn_acc_score)
    print("Epoch %d slot accuracy : " % epoch, np.mean(slot_acc_score))
    print("Latency Per Prediction : %f ms" % latency)
    print("-----------------------------\n")
    
    
    if not os.path.exists("pred-evaluation"):
        os.makedirs("pred-evaluation")
    json.dump(results, open(f'pred-evaluation/{pred_set_name}_preds_full_%d.json' % epoch, 'w'), indent=4)

    scores = {'epoch': epoch, 'loss': loss, 'joint_acc': joint_acc_score, 'joint_turn_acc': joint_turn_acc_score, 'slot_acc': slot_acc_score, 'ave_slot_acc': np.mean(slot_acc_score)}
    
    return scores
